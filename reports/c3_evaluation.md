# Part C3: Iris evaluation

## Pipeline branch

The existing pipeline metadata contains exactly one `evaluate_model` block. `train_model` has exactly two downstream blocks, `save_results` and `evaluate_model`. No duplicate block was added and the pipeline structure was not rebuilt.

## Depth 3 execution results

Command run in `mageai/mageai:latest`:

```text
mage run iris_project iris_classifier --test --runtime-vars '{"max_depth": 3}'
```

The final run exited with code 0. All six block tests passed, and Mage reported `Pipeline run completed.` The evaluation output was:

```text
Confusion matrix (rows = actual, columns = predicted; labels = [0, 1, 2]):
    0  1   2
0  10  0   0
1   0  9   0
2   0  0  11
Evaluation metrics:
   metric  value
 accuracy    1.0
precision    1.0
   recall    1.0
 f1_score    1.0
```

The generated [confusion matrix CSV](c3_confusion_matrix.csv) contains:

```csv
actual_class,0,1,2
0,10,0,0
1,0,9,0
2,0,0,11
```

Complete successful Mage output: [c3_mage_run.log](c3_mage_run.log).

The first implementation attempt stored the matrix in `DataFrame.attrs`; Mage's output serialization did not preserve those attributes for the test, and that run failed with `KeyError`. The test now validates the persisted CSV directly. The first attempt's complete log is retained at [c3_mage_run_initial_test_failure.log](c3_mage_run_initial_test_failure.log); the final run above passed.

## Pipeline metadata used

This is the existing `iris_project/pipelines/iris_classifier/metadata.yaml` content used for the successful run:

```yaml
blocks:
- name: load_iris
  uuid: load_iris
  type: data_loader
  language: python
  upstream_blocks: []
  downstream_blocks: [validate_iris]
- name: validate_iris
  uuid: validate_iris
  type: transformer
  language: python
  upstream_blocks: [load_iris]
  downstream_blocks: [prepare_data]
- name: prepare_data
  uuid: prepare_data
  type: transformer
  language: python
  upstream_blocks: [validate_iris]
  downstream_blocks: [train_model]
- name: train_model
  uuid: train_model
  type: transformer
  language: python
  upstream_blocks: [prepare_data]
  downstream_blocks: [save_results, evaluate_model]
- name: save_results
  uuid: save_results
  type: data_exporter
  language: python
  upstream_blocks: [train_model]
  downstream_blocks: []
- name: evaluate_model
  uuid: evaluate_model
  type: transformer
  language: python
  upstream_blocks: [train_model]
  downstream_blocks: []
name: iris_classifier
uuid: iris_classifier
type: python
variables:
  max_depth: 3
```

## Mage UI and temporary tunnel

Mage UI is running in Docker on port 6789 and returned HTTP 200 locally. The container mounts only `iris_project` at `/home/src/iris_project`; it does not mount the repository root or `.env`. Mage's startup log reported that user authentication is enabled.

`cloudflared` was not installed or on PATH in Windows. A temporary Cloudflare Quick Tunnel was started in a separate Docker container, without credentials or configuration mounts, and returned HTTP 200 when checked. Its temporary public URL is intentionally omitted here. The tunnel was only for the assignment screenshot; no credentials were exposed through it.

To stop the tunnel and Mage UI containers:

```powershell
docker stop iris-cloudflared-c3 iris-mage-ui-c3
docker rm iris-cloudflared-c3 iris-mage-ui-c3
```

To install `cloudflared` on Windows later, download the Windows MSI or executable from [Cloudflare's official downloads page](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/), install it, and reopen PowerShell so the updated PATH is loaded. A Quick Tunnel can then be started with `cloudflared tunnel --url http://localhost:6789`; it is temporary and requires no credentials or account.

The raw tunnel log is excluded from submission because it contains the temporary public URL.
