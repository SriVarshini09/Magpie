"""S2_URL with a generated password (holding @ : / # ?) still parses into connect() fields."""

from app.integrations.s2 import s2_url_parts


def test_password_with_special_characters():
    p = s2_url_parts("user-a1234:p@ss:w/rd#?x@svc-1-dml.aws-virginia-6.svc.singlestore.com:3333/db_x")
    assert p == {"host": "svc-1-dml.aws-virginia-6.svc.singlestore.com", "user": "user-a1234", "password": "p@ss:w/rd#?x",
                 "port": 3333, "database": "db_x"}


def test_plain_and_scheme_urls():
    assert s2_url_parts("u:pw@h:3306/db") == {"host": "h", "user": "u", "password": "pw", "port": 3306, "database": "db"}
    assert s2_url_parts("singlestoredb://u:pw@h:3306/db") is None  # a scheme URL goes to connect() unchanged
    assert s2_url_parts("") is None and s2_url_parts("no-at-sign") is None
    assert s2_url_parts("user name:pw@h:3306/db")["user"] == "user name"  # not fixed silently; the checker flags spaces
