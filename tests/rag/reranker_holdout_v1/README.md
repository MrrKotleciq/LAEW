# Independent multilingual engineering holdout v1

Prepared and labeled before scoring the candidate rerankers. This fixture is
independent of the previous Stage 2B.2 questions, with 32 English/Polish/German
queries, cross-language evidence, multiple documents, version confusion, code,
configuration, project/hybrid scopes and four unsupported questions.

The eight public-document notes are short authored paraphrases/translations, not
copies of complete manuals. Their official source URLs are in `dataset.json`.
Python material refers to version 3.13 documentation. Atlas R2/R3, C6/C7, S7/S8,
their serial numbers, engineering limits and procedures are explicitly fictional
contracts authored for this fixture. They must never be treated as operational
instructions for actual equipment.

Evidence labels are exact source-attributed text atoms established from the notes
before inspecting embeddings, retrieved pools, reranker scores or generated answers.
The absence labels refer to the complete supplied corpus, including the two project
notes. No private production files or measurements are included. Related questions
have `topic_id`; they are not statistically independent paraphrases. This is not
an external expert-blind or naturally sampled industrial benchmark and cannot alone
justify a production default change. Do not edit after freeze to improve a score.
