from vice_next_mcp.batch import BatchRunner, allocate_ports, case_id


def test_case_id_is_canonical():
    assert case_id({"b": 2, "a": 1}) == case_id({"a": 1, "b": 2})


def test_ports_skip_occupied():
    ports = allocate_ports(0, 3, occupied={1})
    assert len(set(ports)) == 3


def test_runner_outputs_and_artifacts(tmp_path):
    def execute(case, artifact, port):
        (artifact / "sample.txt").write_text(str(port))
        return {"executable_hash": "x", "raw_samples": [1]}

    result = BatchRunner(tmp_path, workers=2).run(
        [{"machine": "c64", "variant": i} for i in range(4)], execute
    )
    assert result["progress"] == {"terminal": 4, "total": 4}
    assert all(r["status"] == "passed" for r in result["results"])
