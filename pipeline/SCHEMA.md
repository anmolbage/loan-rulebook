# Product rule file format (`private/products/<product-id>.json`)

One JSON file per loan product (UTF-8, valid JSON, no comments). Every rule MUST carry at least one citation.

```json
{
  "id": "home-loan",                       // kebab-case, unique
  "name": "Home Loan",
  "group": "Housing",                       // Housing | Vehicle | Personal & Education | Gold | Agriculture | MSME/SME | NRLM/SHG & Govt | Staff | General Credit Norms
  "aliases": ["housing loan", "Swagat"],
  "status": "active",                       // active | discontinued | campaign-ended | unclear
  "summary": "2-3 lines: what it is, who it is for, headline amount/ROI.",
  "customer_types": ["salaried", "self-employed", "professional", "pensioner", "farmer", "nri", "staff", "shg", "firm-company", "others"],
  "governing": [
    {"cid": "a1b2c3d4e5f6", "role": "master|amendment|rate|fee|clarification|campaign|format|policy", "note": "what this circular changed"}
  ],
  "sections": [
    {
      "key": "eligibility",                 // eligibility | purpose | quantum | margin | roi | fees | tenure_repayment | security | guarantee_cover | credit_score | income_norms | documents | sanction_powers | restrictions | process | campaign | other
      "title": "Eligibility",
      "rules": [
        {
          "text": "Age 21-60 years at entry; loan to be repaid by age 70.",
          "applies_to": ["salaried"],       // omit or [] = all customer types of this product
          "cite": [{"cid": "a1b2c3d4e5f6", "page": 4, "quote": "verbatim snippet <=200 chars from the circular"}],
          "effective": "2022-04-21",        // date of the circular that set this rule (YYYY-MM-DD), "" if unknown
          "superseded": [                   // OLDER versions of the same rule, newest first (optional)
            {"text": "Age 21-55 ...", "cite": [{"cid": "...", "page": 3, "quote": "..."}], "effective": "2019-06-01"}
          ],
          "confidence": "high"              // high | medium | low (low = ambiguous text / scanned / conflicting)
        }
      ]
    }
  ],
  "checks": [                               // machine-checkable rules for the Proposal Checker (only where circulars give numbers)
    {"field": "age", "op": "between", "value": [21, 60], "applies_to": ["salaried"], "label": "Entry age 21-60", "cite": [{"cid": "...", "page": 4}]}
  ],
  "defences": [                             // typical objections from processing/RO/HO and the circular-backed answer
    {"objection": "Applicant is self-employed without ITR for 3 years", "response": "Circular permits ... ", "cite": [{"cid": "...", "page": 6, "quote": "..."}]}
  ],
  "gaps": ["Points the circulars do not specify (so cannot be a ground of rejection unless another policy says so)"]
}
```

## Checker fields (use only these in `checks.field`)
| field | meaning | ops |
|---|---|---|
| `age` | applicant age in years at application | min, max, between |
| `age_at_maturity` | age at loan closure | max |
| `nmi` | net monthly income (Rs) | min |
| `annual_income` | gross annual income (Rs) | min, max |
| `cibil` | CIBIL / credit score | min |
| `amount` | loan amount requested (Rs) | min, max, between |
| `tenure_months` | repayment period in months | max, between |
| `foir` | (all EMIs incl. proposed) / gross monthly income, percent | max |
| `ltv` | loan / value of asset or security, percent | max |
| `margin` | borrower contribution, percent of cost | min |
| `experience_years` | years in job/business | min |
| `customer_type` | one of customer_types above | in |

`value` is a number, or `[low, high]` for `between`, or a list of strings for `in`. Rupee amounts are plain numbers (1 crore = 10000000).
If a limit differs by slab (e.g. income slab -> FOIR), add one check per slab and put the condition in `label` and `applies_to`.

**Variants.** When checks belong to mutually exclusive options of the same product (repayment option EMI vs bullet, scheme variant, purpose such as purchase vs construction, location metro/urban/rural, loan-amount slab), add `"variant": "<short option name>"` to each such check. The checker lets the user pick one variant and skips checks of other variants. Checks without `variant` always apply. Use identical spelling for the same variant across checks. If a product has several independent dimensions (e.g. loan-amount slab and income slab), prefix the variant with the dimension: `"LTV slab: up to Rs 20 lakh"`, `"Income slab: NMI above Rs 50,000"`; the checker shows one picker per dimension.

**Slab auto-pick.** When a variant is defined by a number (loan amount, net annual income, net monthly income, age, experience), add to the product `"variant_slabs": {"<exact variant name>": {"field": "amount|nai|nmi|age|experience_years", "gt": <exclusive lower bound, optional>, "le": <inclusive upper bound, optional>}}`. `nai` = net annual income (NMI x 12). The checker then selects the slab automatically when every option of that dimension has an entry.

## Rules for extraction
1. The latest circular in force wins. A later circular/circular letter that revises ROI, fees, eligibility etc. replaces the earlier rule; move the old one into `superseded`.
2. Campaign concessions (processing-fee waiver, special ROI) go in section `campaign` with their validity period stated in `text`; set `status` of the rule text to make clear whether the validity date has passed (today is 2026-11-20).
3. Quote verbatim. Never invent numbers. If unsure, set `confidence: "low"` and say why in the text.
4. `cid` is the 12-char `id` from `private/manifest.json`. Page numbers come from the `=== PAGE n ===` markers.
5. Duplicates: the folder `CIRCULAR & UPDATED POLICIES (FY 2022-2023)` duplicates many `2022-2023` files; cite either, but only once.
