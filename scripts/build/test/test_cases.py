from scripts.build.cases import BAD_EXTENSIONS, cases, instance_data, skipped

EXPECT_KEYS = {
    "user", "username", "gh_dir", "git_name", "extensions", "skipped", "gh_extensions", "gh_skipped", "signer",
    "signer_key", "ssh_program",
}  # fmt: skip


def table():
    return cases("/keys", "ssh-ed25519 AAAAsigner jane", "ecdsa-sha2-nistp256 AAAAecdsa jane", {"username": None})


def test_cases_have_unique_names_and_every_expectation():
    names = [case.name for case in table()]

    assert len(names) == len(set(names)) == 32
    assert all(set(case.expect) == EXPECT_KEYS for case in table())


def test_cases_fill_in_the_instance_id_and_defaults():
    by_name = {case.name: case for case in table()}

    assert by_name["no-meta-data"].meta_data == {"instance-id": "ubuntu-wsl"}
    assert by_name["no-meta-data"].expect["username"] is None
    assert by_name["plain-email"].expect["username"] == "jdoe"
    assert by_name["plain-email"].expect["signer_key"] == "/keys/signer"
    assert by_name["signingkey-ecdsa"].expect["signer_key"] == "/keys/ecdsa"


def test_the_shipped_meta_data_case_reads_the_template_with_a_username():
    shipped = next(case for case in table() if case.name == "shipped-meta-data")

    assert shipped.meta_data == {"instance-id": "ubuntu-wsl", "username": "jdoe"}


def test_skipped_entries_are_ascii_with_backslash_escapes():
    assert skipped(["ün.code", "\U0001f600.x", 42, None]) == ["\\xfcn.code", "\\U0001f600.x", "42", "None"]
    assert len(skipped(BAD_EXTENSIONS)) == len(BAD_EXTENSIONS)


def test_instance_data_puts_the_meta_data_under_ds():
    data = instance_data({"username": "jdoe"})

    assert data["ds"] == {"meta_data": {"username": "jdoe"}}
    assert data["v1"]["platform"] == "wsl"
