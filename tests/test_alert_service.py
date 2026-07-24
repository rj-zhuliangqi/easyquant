"""AlertService 单测（P2-4 盘中预警）。"""

from app.services.alert_service import AlertService

_IR = {"root": {"type": "compare", "left": {"type": "field", "name": "close"}, "op": ">", "right": {"type": "const", "value": 0}}}


def test_define_list_delete_rule(db_session):
    svc = AlertService(screener=None)  # check_rules 依赖 screener.run，单测不覆盖
    svc.define_rule(db_session, "涨停预警", _IR)
    rules = svc.list_rules(db_session)
    assert len(rules) == 1
    assert rules[0]["name"] == "涨停预警"
    assert rules[0]["ir"] is not None
    assert rules[0]["enabled"] is True
    assert svc.delete_rule(db_session, rules[0]["id"]) is True
    assert svc.list_rules(db_session) == []


def test_define_overwrite_same_name(db_session):
    svc = AlertService(screener=None)
    svc.define_rule(db_session, "规则", _IR)
    svc.define_rule(db_session, "规则", {"root": {"type": "compare", "left": {"type": "field", "name": "close"}, "op": ">", "right": {"type": "const", "value": 10}}})
    rules = svc.list_rules(db_session)
    assert len(rules) == 1  # 同 name 覆盖


def test_list_events_empty(db_session):
    svc = AlertService(screener=None)
    assert svc.list_events(db_session) == []


def test_delete_nonexistent(db_session):
    svc = AlertService(screener=None)
    assert svc.delete_rule(db_session, 999) is False
