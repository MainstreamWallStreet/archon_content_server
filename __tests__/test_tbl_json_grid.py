def test_tbl_json_missing_rows_handled():
    """Ensure _tbljson_to_grid handles tbl_json without 'rows' key."""
    from src import edgar_cli as ec

    tbl_json = {"headers": ["A", "B"]}
    # function should return grid with only headers row
    grid = ec._tbljson_to_grid(tbl_json)
    assert grid == [["A", "B"]]


def test_tbl_json_dict_rows_expanded():
    """Dictionary rows should be expanded using header order."""
    from src import edgar_cli as ec

    tbl_json = {
        "headers": ["A", "B"],
        "rows": [{"A": "x", "B": "y"}, {"A": "1", "B": "2"}],
    }

    grid = ec._tbljson_to_grid(tbl_json)
    assert grid == [["A", "B"], ["x", "y"], ["1", "2"]]
