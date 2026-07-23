"""StockPoolService 单测（P2-3 选股流水线）。"""

from app.services.stock_pool import StockPoolService


def test_save_and_list(db_session):
    svc = StockPoolService()
    svc.save_pool(db_session, "强势股", ["000001", "000002"])
    pools = svc.list_pools(db_session)
    assert len(pools) == 1
    assert pools[0]["name"] == "强势股"
    assert pools[0]["count"] == 2
    assert pools[0]["codes"] == ["000001", "000002"]


def test_save_overwrite_same_name(db_session):
    svc = StockPoolService()
    svc.save_pool(db_session, "池", ["000001"])
    svc.save_pool(db_session, "池", ["000002", "000003"])  # 覆盖
    pools = svc.list_pools(db_session)
    assert len(pools) == 1  # 同 name 不新增
    assert pools[0]["count"] == 2


def test_get_and_delete(db_session):
    svc = StockPoolService()
    r = svc.save_pool(db_session, "池", ["000001"])
    p = svc.get_pool(db_session, r["id"])
    assert p["codes"] == ["000001"]
    assert svc.delete_pool(db_session, r["id"]) is True
    assert svc.get_pool(db_session, r["id"]) is None
    assert svc.delete_pool(db_session, 999) is False
