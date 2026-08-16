# Accuracy benchmarking

The detector is heuristic software, so the project does not publish a made-up
accuracy percentage. To measure it, create `benchmark_manifest.jsonl` using the
format in `benchmark_manifest.example.jsonl`.

Use a varied, independently labeled set with both classes represented:

- phone and DSLR recordings
- livestreams and screen recordings
- edited films and compressed social-video exports
- multiple AI generators and realistic synthetic clips
- different resolutions, codecs, lighting, motion, and durations

For each item, record the source and why the label is trusted. Do not label a
file only from its filename or from this detector's output.

Run:

```bash
python benchmark.py benchmark_manifest.jsonl --output benchmark_report.json
```

The report includes sample count, class balance, accuracy, precision, recall,
specificity, F1, balanced accuracy, a confusion matrix, and per-item results.
The website's `/api/benchmark` endpoint exposes the same report. If the
manifest is absent, the website says “not measured” rather than showing a
marketing number.