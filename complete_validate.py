def complete_validate(state: GraphState) -> GraphState:
    spec = state.spec

    # 1. Normalize — units to inches, dimension convention to inside,
    #    L/W/D reordering, strength spec parsing ("200# test" -> mullen/200)
    spec = normalize(spec)

    # 2. Apply rules-table defaults for absent fields — flute defaulting,
    #    standard print coverage assumptions. Each write stamps
    #    provenance=DEFAULTED, source="defaults_table:v12"
    spec = apply_defaults(spec, defaults_table)

    # 3. Derive calculated fields — the truckload calculator lives here:
    #    dims + pallet config + trailer -> units, with calc_basis recorded
    spec = derive_quantities(spec, logistics_config)

    # 4. Resolve against plant master data — strength+flute -> stocked
    #    board_code, style -> CoreERP style code. Deterministic lookups;
    #    no match -> gap or flag, never a guess
    spec = resolve_master_data(spec, plant_master)

    # 5. Manufacturability & business checks -> validation_flags:
    #    machine min/max, press color capacity, tooling existence for
    #    die-cuts, min run qty, credit status, ship-to distance
    spec = run_checks(spec, plant_master, customer_master)

    # 6. Compute gaps (any price-affecting Field with value=None),
    #    set status: "validated" if clean else still "draft"
    spec = finalize_gap_report(spec)

    return state.model_copy(update={"spec": spec})

def route_after_validation(spec: QuoteSpec) -> str:
    if spec.gaps or any(f in BLOCKING_FLAGS for f in spec.validation_flags):
        return "clarify"          # interrupt: estimator resolves, or drafts customer email
    if has_unconfirmed_inferred_fields(spec):
        return "clarify"          # inferred values never reach pricing unreviewed
    return "price"                # freeze and proceed
