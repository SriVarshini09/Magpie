"""Reference-design reading never touches a never-request host, on any path (PLAN §3.16 rule 3, §3.18)."""

from __future__ import annotations

import pytest

from app.intake.http import check_reference_url, drop_never_request
from app.stores.http import HostNotAllowed


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B0CTMM4LWK", "https://www.digikey.com/en/products/detail/x", "https://www.ebay.com/itm/1",
    "https://www.walmart.com/ip/1", "https://www.microcenter.com/product/1", "https://octopart.com/x", "https://www.robotshop.com/x",
])
def test_never_request_host_is_refused_even_when_the_user_pasted_it(url):
    for pasted in (False, True):
        with pytest.raises(HostNotAllowed) as exc:
            check_reference_url(url, user_pasted=pasted)
        assert exc.value.refusal["rule"] == "reference_host_not_allowed"


def test_reference_allowlist():
    assert check_reference_url("https://docs.px4.io/v1.14/en/frames_multicopter/holybro_x500V2_pixhawk5x")
    assert check_reference_url("https://raw.githubusercontent.com/TheRobotStudio/SO-ARM100/main/README.md")
    with pytest.raises(HostNotAllowed):
        check_reference_url("https://some-blog.example/drone-build")
    assert check_reference_url("https://some-blog.example/drone-build", user_pasted=True)
    with pytest.raises(HostNotAllowed):
        check_reference_url("http://docs.px4.io/x")


def test_search_results_pointing_at_never_request_hosts_are_dropped():
    hits = [{"url": "https://docs.px4.io/a"}, {"url": "https://www.amazon.com/dp/B0"}, {"url": "https://www.ebay.com/itm/1"}, {"url": ""}]
    assert drop_never_request(hits) == [{"url": "https://docs.px4.io/a"}]
