$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw "Project virtualenv Python was not found at $python"
}

$baseLogDir = Join-Path $projectRoot 'reports\rabbitmq_logs\d3'
$runId = Get-Date -Format 'yyyyMMdd_HHmmss'
$runLogDir = Join-Path $baseLogDir $runId
New-Item -ItemType Directory -Path $runLogDir -Force | Out-Null
$metadataPath = Join-Path $runLogDir 'run_metadata.txt'
Set-Content -LiteralPath $metadataPath -Value "run_id=$runId"
Add-Content -LiteralPath $metadataPath -Value "python=$python"

$drivers = @(
    @{ Name = 'Ravi'; Pattern = 'bangalore.koramangala.*' },
    @{ Name = 'Priya'; Pattern = 'bangalore.indiranagar.*' },
    @{ Name = 'Arjun'; Pattern = 'bangalore.*.ride' },
    @{ Name = 'Meena'; Pattern = 'bangalore.*.food' },
    @{ Name = 'Karthik'; Pattern = 'chennai.tnagar.food' },
    @{ Name = 'Control'; Pattern = 'bangalore.#' }
)

$started = [System.Collections.Generic.List[object]]::new()
$stopAt = $null
$elapsed = $null
$dispatcherStartAt = $null
$runStopwatch = $null

function Start-LoggedPythonProcess {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [string]$Kind
    )

    $stdoutPath = Join-Path $runLogDir "$Name.stdout.log"
    $stderrPath = Join-Path $runLogDir "$Name.stderr.log"
    $argumentLine = ($Arguments | ForEach-Object {
        if ($_ -match '[\s*#]') { '"' + $_.Replace('"', '\"') + '"' } else { $_ }
    }) -join ' '
    $process = Start-Process -FilePath $python -ArgumentList $argumentLine `
        -WorkingDirectory $projectRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru -WindowStyle Hidden

    $record = [pscustomobject]@{
        Name = $Name
        Kind = $Kind
        PID = $process.Id
        Stdout = $stdoutPath
        Stderr = $stderrPath
    }
    $started.Add($record)
    Add-Content -LiteralPath $metadataPath -Value "started=$Kind name=$Name pid=$($process.Id)"
    return $record
}

function Stop-OnlyStartedProcesses {
    foreach ($record in @($started | Sort-Object @{ Expression = { if ($_.Kind -eq 'dispatcher') { 0 } else { 1 } } })) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.PID)" -ErrorAction SilentlyContinue
        if (-not $process) {
            Add-Content -LiteralPath $metadataPath -Value "already_exited=$($record.Kind) name=$($record.Name) pid=$($record.PID)"
            continue
        }

        $expectedCommand = if ($record.Kind -eq 'driver') {
            "-m stream.driver $($record.Name)"
        } else {
            '-m stream.dispatcher'
        }
        if ($process.Name -ne 'python.exe' -or $process.CommandLine -notlike "*$expectedCommand*") {
            Add-Content -LiteralPath $metadataPath -Value "refused_to_stop_pid=$($record.PID) reason=process_identity_mismatch"
            throw "Refusing to stop PID $($record.PID): it no longer matches this helper's $($record.Kind) process."
        }

        Stop-Process -Id $record.PID -Force
        Add-Content -LiteralPath $metadataPath -Value "stopped=$($record.Kind) name=$($record.Name) pid=$($record.PID)"
    }
}

try {
    $health = docker inspect --format '{{.State.Health.Status}}' freshcart-rabbitmq
    if ($LASTEXITCODE -ne 0 -or $health.Trim() -ne 'healthy') {
        throw 'RabbitMQ container freshcart-rabbitmq is not healthy; refusing to start D3.'
    }

    $readyDeadline = (Get-Date).AddSeconds(60)
    foreach ($driver in $drivers) {
        $null = Start-LoggedPythonProcess -Name $driver.Name `
            -Arguments @('-u', '-m', 'stream.driver', $driver.Name, $driver.Pattern) `
            -Kind 'driver'
    }

    $allReady = $false
    do {
        $allReady = $true
        foreach ($record in $started | Where-Object { $_.Kind -eq 'driver' }) {
            $output = if (Test-Path -LiteralPath $record.Stdout) {
                Get-Content -LiteralPath $record.Stdout -Raw -ErrorAction SilentlyContinue
            } else { '' }
            if ($output -notmatch "\[$($record.Name)\] listening with binding ") {
                $allReady = $false
                $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.PID)" -ErrorAction SilentlyContinue
                if (-not $process) {
                    $errorText = Get-Content -LiteralPath $record.Stderr -Raw -ErrorAction SilentlyContinue
                    throw "Driver $($record.Name) exited before listening. See $($record.Stderr). $errorText"
                }
            }
        }
        if ($allReady) { break }
        Start-Sleep -Milliseconds 250
    } while ((Get-Date) -lt $readyDeadline)

    if (-not $allReady) {
        throw "Not all six drivers reported listening within 60 seconds. Logs: $runLogDir"
    }

    foreach ($driver in $drivers) {
        Add-Content -LiteralPath $metadataPath -Value "driver_ready=$($driver.Name) pattern=$($driver.Pattern)"
    }

    $dispatcher = Start-LoggedPythonProcess -Name 'dispatcher' `
        -Arguments @('-u', '-m', 'stream.dispatcher') `
        -Kind 'dispatcher'
    $dispatcherProcess = Get-Process -Id $dispatcher.PID
    $dispatcherStartAt = [DateTimeOffset]::new($dispatcherProcess.StartTime)
    $runStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    Add-Content -LiteralPath $metadataPath -Value "dispatcher_start_local=$($dispatcherStartAt.ToString('o'))"
    Write-Output "D3_RUN_ID=$runId"
    Write-Output "D3_LOG_DIR=$runLogDir"
    Write-Output "D3_START_LOCAL=$($dispatcherStartAt.ToString('o'))"
    Write-Output 'ALL_SIX_DRIVERS_LISTENING=true'

    while ($runStopwatch.Elapsed.TotalSeconds -lt 60) {
        $dispatcherProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$($dispatcher.PID)" -ErrorAction SilentlyContinue
        if (-not $dispatcherProcess) {
            throw "Dispatcher exited before 60 seconds. See $($dispatcher.Stderr)."
        }
        Start-Sleep -Milliseconds 250
    }

    $stopAt = [DateTimeOffset]::Now
    $elapsed = $stopAt - $dispatcherStartAt
    Add-Content -LiteralPath $metadataPath -Value "dispatcher_stop_local=$($stopAt.ToString('o'))"
    Add-Content -LiteralPath $metadataPath -Value "elapsed=$($elapsed.ToString())"
    Add-Content -LiteralPath $metadataPath -Value 'minimum_duration_seconds=60'
    Write-Output "D3_STOP_LOCAL=$($stopAt.ToString('o'))"
    Write-Output "D3_ELAPSED=$($elapsed.ToString())"
}
finally {
    if ($runStopwatch -and -not $stopAt) {
        $stopAt = [DateTimeOffset]::Now
        $elapsed = $stopAt - $dispatcherStartAt
        Add-Content -LiteralPath $metadataPath -Value "dispatcher_stop_local=$($stopAt.ToString('o'))"
        Add-Content -LiteralPath $metadataPath -Value "elapsed=$($elapsed.ToString())"
        Add-Content -LiteralPath $metadataPath -Value 'run_interrupted_or_failed_before_60_seconds=true'
        Write-Output "D3_STOP_LOCAL=$($stopAt.ToString('o'))"
        Write-Output "D3_ELAPSED=$($elapsed.ToString())"
    }
    Stop-OnlyStartedProcesses
    Write-Output 'HELPER_OWNED_PROCESSES_STOPPED=true'
}
