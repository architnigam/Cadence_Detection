# Independent annotation guide

## Independence and review workflow

1. Read the original artifact and inventory every source unit before looking at detector output. Reference native parsing and manual transcriptions are aids, not validated extraction results.
2. Choose and freeze development/held-out units before tuning. Keep repeated tables/screenshots together to avoid leakage. Record any split revision and invalidate comparisons to the previous split.
3. Assign opaque document/block IDs. Freeze normalized text and its SHA-256. Preserve original page/slide, paragraph/table cell and image location. OCR corrections must retain a source mapping.
4. Label every occurrence, including repeats, initials, headers/footers, notes, table cells and screenshot-only text. Set `image_only` for text whose original evidence is an image, even after OCR transcription.
5. Review negative blocks explicitly. Block status stays pending until the entire block has been checked. A literal catalogue can seed occurrences but cannot establish completeness.
6. A different teammate reviews each block and resolves disagreements with Person 5. Log uncertain labels. Only then mark the block and all its labels adjudicated. Do not copy model predictions into ground truth.
7. Freeze the gold version and document reviewer IDs. Score the held-out subset once decisions have frozen. Reevaluate when code changes and report which gold version was used.

## Label rules

| Type | What to label | Hard/negative distinction |
|---|---|---|
| PERSON | Full name, initials plus surname, contextual single-name reference | Organizations, product names and role titles are negative |
| EMAIL | Whole mailbox/address, including corporate mail | Domain/product mention alone is negative |
| PHONE | Whole number including prefix/extension where present | Accept supplied short synthetic formats with contact context |
| EMPLOYEE_ID / DIRECTOR_ID / VENDOR_PERSON_ID | Complete personal identifier including prefix | Policy, questionnaire, control and incident IDs are negative |
| DATE_OF_BIRTH | Date explicitly tied to a person's birth | Document version, incident, review and hiring dates are negative |
| HOME_ADDRESS | Complete personal residential address | Generic office location without personal context is negative |
| NATIONAL_ID / TAX_ID / PASSPORT | Whole contextual government/tax/travel ID | Synthetic invalid checksums remain labeled when the source identifies the personal field |
| BANK_ACCOUNT / PAYMENT_CARD | Complete contextual personal account/card identifier | Money, transaction amounts and unassociated digit strings are negative |
| PARTIAL_IDENTIFIER | Visible masked identifier or ending digits with personal identifier context | Preserve its parent type as optional metadata. Mask all visible personal digits |
| PHOTOGRAPH_REGION / SIGNATURE_REGION | Image-region bounding box | Separate from text detections. Do not assign text offsets |

Use maximal meaningful non-overlapping text spans. Do not label both a full name and an embedded surname as separate occurrences. For possessives, label the name without the possessive suffix. Include ID prefixes and internal spaces/hyphens. Do not include punctuation around the value or adjacent field labels. For generic dates/addresses, record why personal context makes them PII.

A repeated abbreviated name links only within its document. The policy and organizational deck use different incumbents. Do not merge them into one authoritative directory.

## Source priorities and actual starter scope

- PPTX: all nine slides need review. Prioritize slides 3–5 contact/org charts, slides 6–7 RACI initials, slide 8 directory. Include notes/grouped shapes/hidden content before declaring extraction complete.
- DOCX: table 5 contains named users. Review all 16 tables, cover/version controls, paragraphs, text boxes, headers/footers and all 41 media entries. Six media entries require SVG/EMF conversion review. Native paragraphs/cells do not account for every embedded or nested item.
- Policy: all 35 pages are scanned. Prioritize p9 identity screenshot, p18 signed attestation, p19 user screenshot, p20 audit log, p22 incident narrative, p23 customer correspondence, p25 offshore roster, p28 badge, p32 RACI. Crop and inspect small screenshot text separately.
- The local starter contains independently catalogued native occurrences and manually transcribed p22 section 16.5 and p23 section 16.8. It does not cover all policy pages or all DOCX embedded images. No team-adjudicated full gold set exists yet.

Local files: `data/annotations/local_source/source_reference.json`, `review_queue.json` and `local_source_catalogue.json`. They contain source PII and are ignored by Git. Keep them local. The synthetic fixture is safe to version. Never log annotated values or send unredacted source text downstream.

## Structure/context rubric

Agree source checks before examining extracted results. Use representative positive/negative checks from every selected unit, including small screenshots. Equal dimension weights are a team proposal, because the brief sets 80% without prescribing a formula.

| Dimension | A check passes when |
|---|---|
| Headings | The heading text survives and attaches to the correct content |
| Reading order | Adjacent source units appear in the intended reading sequence |
| Block boundaries | Paragraphs/list items remain separate and sentence boundaries do not merge |
| Table relationships | A cell retains the correct row, column and header association |
| Neighboring context | A finding retains the preceding and succeeding clause/block without unrelated content interleaving |

Score each dimension using passed/total checks and retain evidence locations. Explicitly mark a dimension N/A with a reason, then renormalize across applicable dimensions. Do not mark a failed/missing table N/A. Report >=80% separately for each document. Independently align source transcription and OCR text for character accuracy, which is a separate measure.
