from sqlalchemy import text

from lotto_model.ingestion.derived import derive_context


def coverage(engine):
    with engine.connect() as conn:

        def query(sql):
            return [dict(r) for r in conn.execute(text(sql)).mappings()]

        years = query(
            "SELECT EXTRACT(YEAR FROM draw_date)::int AS year,status,count(*) "
            "AS draws,min(draw_date) AS first,max(draw_date) AS last "
            "FROM draws GROUP BY 1,2 ORDER BY 1,2"
        )
        observations = query(
            "SELECT status,count(*) AS records FROM source_observations GROUP BY status"
        )
        prizes = conn.scalar(text("SELECT count(*) FROM prize_tiers"))
        context = conn.scalar(text("SELECT count(*) FROM draw_context"))
        rules = conn.scalar(text("SELECT count(*) FROM rule_regimes"))
        calendar = conn.scalar(text("SELECT count(*) FROM calendar_dates"))
        dataset_counts = {
            "prize_breakdowns": prizes,
            "jackpot_context": context,
            "rules_and_prices": rules,
            "rule_attributes": conn.scalar(
                text("SELECT count(*) FROM rule_attributes")
            ),
            "calendar": calendar,
            "calendar_events": conn.scalar(
                text("SELECT count(*) FROM calendar_events")
            ),
            "winning_ticket_reports": conn.scalar(
                text("SELECT count(*) FROM winning_ticket_reports")
            ),
            "official_period_metrics": conn.scalar(
                text("SELECT count(*) FROM official_period_metrics")
            ),
        }
        derived = []
        for row in query(
            "SELECT d.id,d.draw_date,d.rule_id,c.outcome FROM draws d "
            "LEFT JOIN draw_context c "
            "ON c.draw_id=d.id AND NOT c.disputed "
            "WHERE d.status='accepted' ORDER BY draw_date"
        ):
            row["mains"] = list(
                conn.execute(
                    text(
                        "SELECT number FROM draw_numbers "
                        "WHERE draw_id=:d AND role='main' ORDER BY number"
                    ),
                    {"d": row["id"]},
                ).scalars()
            )
            row["prizes"] = query_prizes(conn, row["id"])
            row["continuous_from_previous"] = False
            if derived:
                previous = derived[-1]
                days = conn.execute(
                    text(
                        "SELECT day,scheduled FROM calendar_dates "
                        "WHERE day>:previous AND day<=:current ORDER BY day"
                    ),
                    {"previous": previous["draw_date"], "current": row["draw_date"]},
                ).all()
                row["continuous_from_previous"] = (
                    previous["rule_id"] == row["rule_id"]
                    and len(days) == (row["draw_date"] - previous["draw_date"]).days
                    and all(s is not None for _, s in days)
                    and sum(s for _, s in days) == 1
                    and bool(days)
                    and days[-1][1] is True
                )
            derived.append(row)
        values = derive_context(derived)
        dataset_counts.update(
            rollover_context=len(values),
            prize_value_summaries=len(values),
            number_descriptors=len(values),
            provenance=conn.scalar(text("SELECT count(*) FROM raw_artifacts")),
        )
        return dict(
            version=1,
            years=years,
            observations=observations,
            observation_coverage=query(
                "SELECT s.code AS source,o.status,o.payload->>'game' AS game, "
                "EXTRACT(YEAR FROM (o.payload->>'draw_date')::date)::int AS year, "
                "count(*) AS records,min(o.payload->>'draw_date') AS first, "
                "max(o.payload->>'draw_date') AS last FROM source_observations o "
                "JOIN raw_artifacts a ON a.id=o.artifact_id "
                "JOIN sources s ON s.id=a.source_id GROUP BY 1,2,3,4 ORDER BY 1,4,2"
            ),
            field_missingness=query(
                "SELECT count(*) AS observed_records, "
                "count(*) FILTER (WHERE payload->>'bonus' IS NULL) AS missing_bonus, "
                "count(*) FILTER (WHERE payload->>'jackpot' IS NULL) "
                "AS missing_jackpot, "
                "count(*) FILTER (WHERE payload->>'outcome' IS NULL) "
                "AS missing_outcome, "
                "count(*) FILTER (WHERE payload->'prizes'='[]'::jsonb) "
                "AS missing_prizes "
                "FROM source_observations"
            )[0],
            prize_missingness=query(
                "SELECT count(*) AS tiers, "
                "count(*) FILTER (WHERE winners IS NULL) AS missing_winners, "
                "count(*) FILTER (WHERE original_amount IS NULL) AS missing_amount, "
                "count(*) FILTER (WHERE currency IS NULL) AS missing_currency, "
                "count(*) FILTER (WHERE prize_type='unresolved') AS unresolved_type "
                "FROM prize_tiers"
            )[0],
            regimes=query(
                "SELECT r.code,r.starts_on,r.ends_on,r.pool,r.evidence_url, "
                "count(d.id) AS draws, "
                "count(d.id) FILTER(WHERE d.status='accepted') AS accepted, "
                "count(d.id) FILTER(WHERE d.status='quarantined') AS quarantined "
                "FROM rule_regimes r LEFT JOIN draws d "
                "ON d.rule_id=r.id GROUP BY r.id ORDER BY starts_on"
            ),
            issues=query(
                "SELECT kind,count(*) AS records FROM quality_issues "
                "WHERE resolved_at IS NULL GROUP BY kind"
            ),
            checkpoints=query(
                "SELECT status,count(*) AS urls FROM fetch_checkpoints GROUP BY status"
            ),
            datasets={
                k: dict(
                    records=v,
                    availability="collected" if v else "not_collected_or_unavailable",
                )
                for k, v in dataset_counts.items()
            },
            expected_coverage=None,
            expected_coverage_reason=(
                "Full historical schedules and exceptions not verified"
            ),
            derived=values,
        )


def query_prizes(conn, draw):
    return [
        dict(r)
        for r in conn.execute(
            text(
                "SELECT p.* FROM prize_tiers p WHERE draw_id=:d AND NOT EXISTS "
                "(SELECT 1 FROM quality_issues q WHERE q.draw_id=p.draw_id "
                "AND q.kind='prize_conflict:'||p.tier AND q.resolved_at IS NULL)"
            ),
            {"d": draw},
        ).mappings()
    ]


MANDATORY = ("dated_draws", "verified_rules", "prize_breakdowns", "jackpot_context")


def acquisition_status(conn):
    """Measured acquisition availability; never declares phase completion itself."""

    def one(sql):
        return dict(conn.execute(text(sql)).mappings().one())

    draws = one(
        "SELECT count(*) FILTER (WHERE d.status='accepted') AS accepted, "
        "count(*) FILTER (WHERE d.status='quarantined') AS quarantined, "
        "count(*) FILTER (WHERE d.status='pending') AS pending, "
        "min(d.draw_date) FILTER (WHERE d.status='accepted') AS first, "
        "max(d.draw_date) FILTER (WHERE d.status='accepted') AS last "
        "FROM draws d JOIN games g ON g.id=d.game_id WHERE g.code='lotto'"
    )
    fields = one(
        "SELECT count(*) FILTER (WHERE EXISTS (SELECT 1 FROM draw_numbers n "
        "WHERE n.draw_id=d.id AND n.role='bonus')) AS with_bonus, "
        "count(*) FILTER (WHERE EXISTS (SELECT 1 FROM prize_tiers p "
        "WHERE p.draw_id=d.id)) AS with_prizes, "
        "count(*) FILTER (WHERE EXISTS (SELECT 1 FROM draw_context c "
        "WHERE c.draw_id=d.id AND c.jackpot_amount IS NOT NULL "
        "AND NOT c.disputed)) AS with_jackpot, "
        "count(*) FILTER (WHERE EXISTS (SELECT 1 FROM draw_context c "
        "WHERE c.draw_id=d.id AND c.outcome IS NOT NULL "
        "AND NOT c.disputed)) AS with_outcome "
        "FROM draws d JOIN games g ON g.id=d.game_id "
        "WHERE g.code='lotto' AND d.status='accepted'"
    )
    observations = one(
        "SELECT count(*) FILTER (WHERE status='staged') AS staged, "
        "count(*) FILTER (WHERE payload->>'observation_kind'='undated') AS undated, "
        "count(*) FILTER (WHERE status='quarantined') AS quarantined "
        "FROM source_observations"
    )
    rules = conn.scalar(
        text(
            "SELECT count(*) FROM rule_regimes r JOIN games g ON g.id=r.game_id "
            "WHERE g.code='lotto' AND r.evidence_url IS NOT NULL"
        )
    )
    annual = conn.scalar(text("SELECT count(*) FROM official_period_metrics"))
    present = {
        "dated_draws": draws["accepted"] > 0,
        "verified_rules": rules > 0,
        "prize_breakdowns": fields["with_prizes"] > 0,
        "jackpot_context": fields["with_jackpot"] > 0,
    }
    return dict(
        version=1,
        dated_main_lotto=draws,
        accepted_field_coverage=fields,
        evidence_backed_rules=rules,
        staged_observations=observations,
        annual_all_games_metrics=annual,
        annual_metrics_scope="All games, annual; never draw-level coverage",
        mandatory_inputs={k: "present" if present[k] else "missing" for k in MANDATORY},
        outstanding=[k for k in MANDATORY if not present[k]],
        complete=False,
        complete_reason=(
            "Completion requires a reviewed acquisition assessment, idempotent "
            "replay, isolated reconstruction and backup restore; measured "
            "availability alone never completes phase 2"
        ),
    )
