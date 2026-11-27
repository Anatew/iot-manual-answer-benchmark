# IoT Manual Answer Benchmark

A reproducible answer-evaluation exercise built around a fictional temperature-monitoring device. The dataset contains 32 answerable questions and eight intentionally unanswerable questions. Each answerable example includes a reference answer, accepted wording variants where applicable, and its source section.

## Quick start

With Python 3.11 or newer:

```sh
python benchmark.py demo
python -m unittest -v
```

The demo compares an always-answer keyword baseline with a keyword baseline that abstains when retrieval score is low or tied. Both run locally.

## Demo results

| Baseline | Answer match | Citation match | Abstention | Strict pass |
| --- | ---: | ---: | ---: | ---: |
| Keyword | 29/32 | 29/32 | 0/8 | 29/40 |
| With abstention | 28/32 | 28/32 | 8/8 | 36/40 |

On this small fixture, abstention prevented all eight unsupported answers. It also reduced correct answers on the supported questions by one, which is why the report breaks out both metrics.

## Score your own answers

For each question ID in `data/questions.jsonl`, put one JSON object in a JSONL file. For example:

```json
{"id":"q01","answer":"60 seconds","citations":["sensor"]}
```

Use `"answer":null,"citations":[]` to abstain. Evaluate one or more complete prediction files:

```sh
python benchmark.py demo --export outputs
python benchmark.py --report report.json evaluate outputs/keyword.jsonl outputs/with-abstention.jsonl
```

## What the benchmark measures

- **Answer match** compares normalized text with the reference answer and accepted variants.
- **Citation match** compares the submitted section IDs with the annotated set.
- **Abstention** measures how often the system declines questions the manual cannot answer.
- **Strict pass** requires both the correct answer behavior and the correct citations.

The report includes every prediction for inspecting errors. The rubric is deliberately deterministic. It evaluates reference matches and citation IDs, so review paraphrases and whether evidence truly supports an answer before drawing conclusions about an external model.
