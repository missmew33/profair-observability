from __future__ import annotations

REQUIRED_COLUMNS = {
    "fair_id",
    "edition_year",
    "participation_id",
    "organisation_id",
    "person_id",
    "sex_gender_classification",
    "sex_gender_confidence",
    "function_code",
    "hierarchy_code",
    "country_code",
    "continent",
    "total_area_m2",
    "physical_corpus_eligible",
}

FORBIDDEN_PUBLIC_COLUMNS = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "surname",
    "email",
    "telephone",
    "phone",
    "mobile",
    "address",
    "postal_address",
    "linkedin",
    "date_of_birth",
    "birth_date",
}
