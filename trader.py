"""
IMC Prosperity 4 — Round 1: "Trading groundwork"
Products:
  - ASH_COATED_OSMIUM     (position limit 80, stable around 10000)
  - INTARIAN_PEPPER_ROOT  (position limit 80, drifts day-to-day, noisy intraday)

Strategy:
  - ASH_COATED_OSMIUM: fixed-fair-value market making at 10000. Take any order
    that crosses fair +/- take_width; quote around fair with a 1-tick spread
    while respecting position limits.
  - INTARIAN_PEPPER_ROOT: dynamic fair value derived from the order-book
    "big-volume" mid (ignores thin quotes that are likely noise). Same take +
    market-make framework, tuned to the noisier intraday behaviour.
"""

from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import math


# --- product constants --------------------------------------------------------

ASH = "ASH_COATED_OSMIUM"
PEPPER = "INTARIAN_PEPPER_ROOT"

POSITION_LIMIT = {
    ASH: 80,
    PEPPER: 80,
}

# Tunable per-product parameters.
PARAMS = {
    ASH: {
        "fair_value": 10000,
        "take_width": 3,        # take any order at fair -/+ take_width
        "clear_width": 1,       # flatten at fair when holding inventory
        "disregard_edge": 1,    # don't pennny orders inside this edge
        "join_edge": 2,         # join (match) best level within this edge
        "default_edge": 3,      # otherwise quote at fair +/- default_edge
        "soft_position_limit": 50,
    },
    PEPPER: {
        "take_width": 2,
        "clear_width": 0,
        "prevent_adverse": True,
        "adverse_volume": 10,
        "reversion_beta": -0.229,  # short-term reversion coefficient on returns
        "disregard_edge": 1,
        "join_edge": 0,
        "default_edge": 2,
    },
}


class Trader:
    # bid() is only used in Round 2 per the spec, but safe to keep.
    def bid(self):
        return 15

    def __init__(self, params=None):
        self.params = params if params is not None else PARAMS
        self.LIMIT = POSITION_LIMIT

        # Optional env-var override used by gridsearch.py.
        # Format: TRADER_PARAMS='{"ASH_COATED_OSMIUM": {"take_width": 2}, ...}'
        # Unknown keys are ignored, so it's safe in all environments.
        import os as _os
        import json as _json
        raw = _os.environ.get("TRADER_PARAMS")
        if raw:
            try:
                override = _json.loads(raw)
                if isinstance(override, dict):
                    for product, patch in override.items():
                        if product in self.params and isinstance(patch, dict):
                            self.params[product].update(patch)
            except Exception:
                pass

    # -- helpers ---------------------------------------------------------------

    def _best_ask(self, od: OrderDepth):
        return min(od.sell_orders.keys()) if od.sell_orders else None

    def _best_bid(self, od: OrderDepth):
        return max(od.buy_orders.keys()) if od.buy_orders else None

    def _pepper_fair_value(self, od: OrderDepth, trader_state: Dict) -> float:
        """Use the 'big-volume' mid as fair; apply a mild reversion nudge."""
        if not od.sell_orders or not od.buy_orders:
            return trader_state.get("pepper_last_price", None)

        best_ask = min(od.sell_orders.keys())
        best_bid = max(od.buy_orders.keys())

        adv = self.params[PEPPER]["adverse_volume"]
        filt_asks = [p for p, v in od.sell_orders.items() if abs(v) >= adv]
        filt_bids = [p for p, v in od.buy_orders.items() if abs(v) >= adv]
        mm_ask = min(filt_asks) if filt_asks else best_ask
        mm_bid = max(filt_bids) if filt_bids else best_bid
        mm_mid = (mm_ask + mm_bid) / 2.0

        last = trader_state.get("pepper_last_price")
        if last is not None and last > 0:
            ret = (mm_mid - last) / last
            pred = mm_mid + mm_mid * ret * self.params[PEPPER]["reversion_beta"]
        else:
            pred = mm_mid

        trader_state["pepper_last_price"] = mm_mid
        return pred

    # -- order-generation primitives ------------------------------------------

    def take_best_orders(self, product, fair_value, take_width, orders, od,
                         position, buy_vol, sell_vol,
                         prevent_adverse=False, adverse_volume=0):
        limit = self.LIMIT[product]

        if od.sell_orders:
            best_ask = min(od.sell_orders.keys())
            best_ask_qty = -od.sell_orders[best_ask]  # convert to positive
            if (not prevent_adverse or abs(best_ask_qty) <= adverse_volume) \
                    and best_ask <= fair_value - take_width:
                qty = min(best_ask_qty, limit - position - buy_vol)
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_vol += qty

        if od.buy_orders:
            best_bid = max(od.buy_orders.keys())
            best_bid_qty = od.buy_orders[best_bid]
            if (not prevent_adverse or abs(best_bid_qty) <= adverse_volume) \
                    and best_bid >= fair_value + take_width:
                qty = min(best_bid_qty, limit + position - sell_vol)
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_vol += qty

        return buy_vol, sell_vol

    def clear_position_order(self, product, fair_value, width, orders, od,
                             position, buy_vol, sell_vol):
        pos_after_take = position + buy_vol - sell_vol
        fair_bid = math.floor(fair_value)
        fair_ask = math.ceil(fair_value)
        limit = self.LIMIT[product]
        buy_capacity = limit - (position + buy_vol)
        sell_capacity = limit + (position - sell_vol)

        if pos_after_take > 0 and fair_ask + width in od.buy_orders:
            clear = min(od.buy_orders[fair_ask + width], pos_after_take)
            sent = min(sell_capacity, clear)
            if sent > 0:
                orders.append(Order(product, fair_ask + width, -sent))
                sell_vol += sent

        if pos_after_take < 0 and fair_bid - width in od.sell_orders:
            clear = min(abs(od.sell_orders[fair_bid - width]), -pos_after_take)
            sent = min(buy_capacity, clear)
            if sent > 0:
                orders.append(Order(product, fair_bid - width, sent))
                buy_vol += sent

        return buy_vol, sell_vol

    def make_orders(self, product, od, fair_value, position, buy_vol, sell_vol,
                    disregard_edge, join_edge, default_edge,
                    soft_position_limit=0):
        orders: List[Order] = []

        asks_above = [p for p in od.sell_orders if p > fair_value + disregard_edge]
        bids_below = [p for p in od.buy_orders if p < fair_value - disregard_edge]
        best_ask_above = min(asks_above) if asks_above else None
        best_bid_below = max(bids_below) if bids_below else None

        # Build our ask price
        ask = round(fair_value + default_edge)
        if best_ask_above is not None:
            if best_ask_above - fair_value <= join_edge:
                ask = best_ask_above     # join
            else:
                ask = best_ask_above - 1  # penny

        # Build our bid price
        bid = round(fair_value - default_edge)
        if best_bid_below is not None:
            if fair_value - best_bid_below <= join_edge:
                bid = best_bid_below
            else:
                bid = best_bid_below + 1

        # Inventory-skew toward flat using soft limit
        if soft_position_limit > 0:
            if position > soft_position_limit:
                ask -= 1
            elif position < -soft_position_limit:
                bid += 1

        limit = self.LIMIT[product]
        buy_qty = limit - (position + buy_vol)
        sell_qty = limit + (position - sell_vol)

        if buy_qty > 0:
            orders.append(Order(product, int(bid), buy_qty))
        if sell_qty > 0:
            orders.append(Order(product, int(ask), -sell_qty))

        return orders

    # -- per-product drivers ---------------------------------------------------

    def trade_ash(self, state: TradingState) -> List[Order]:
        if ASH not in state.order_depths:
            return []
        p = self.params[ASH]
        od = state.order_depths[ASH]
        position = state.position.get(ASH, 0)
        fair = p["fair_value"]

        orders: List[Order] = []
        buy_vol, sell_vol = self.take_best_orders(
            ASH, fair, p["take_width"], orders, od, position, 0, 0
        )
        buy_vol, sell_vol = self.clear_position_order(
            ASH, fair, p["clear_width"], orders, od, position, buy_vol, sell_vol
        )
        orders += self.make_orders(
            ASH, od, fair, position, buy_vol, sell_vol,
            p["disregard_edge"], p["join_edge"], p["default_edge"],
            soft_position_limit=p["soft_position_limit"],
        )
        return orders

    def trade_pepper(self, state: TradingState, trader_state: Dict) -> List[Order]:
        if PEPPER not in state.order_depths:
            return []
        p = self.params[PEPPER]
        od = state.order_depths[PEPPER]
        position = state.position.get(PEPPER, 0)
        fair = self._pepper_fair_value(od, trader_state)
        if fair is None:
            return []

        orders: List[Order] = []
        buy_vol, sell_vol = self.take_best_orders(
            PEPPER, fair, p["take_width"], orders, od, position, 0, 0,
            prevent_adverse=p["prevent_adverse"],
            adverse_volume=p["adverse_volume"],
        )
        buy_vol, sell_vol = self.clear_position_order(
            PEPPER, fair, p["clear_width"], orders, od, position, buy_vol, sell_vol
        )
        orders += self.make_orders(
            PEPPER, od, fair, position, buy_vol, sell_vol,
            p["disregard_edge"], p["join_edge"], p["default_edge"],
        )
        return orders

    # -- main entry point ------------------------------------------------------

    def run(self, state: TradingState):
        # Persist light state between iterations (traderData is a string; JSON works).
        import json
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
            if not isinstance(trader_state, dict):
                trader_state = {}
        except Exception:
            trader_state = {}

        result: Dict[str, List[Order]] = {}

        ash_orders = self.trade_ash(state)
        if ash_orders:
            result[ASH] = ash_orders

        pepper_orders = self.trade_pepper(state, trader_state)
        if pepper_orders:
            result[PEPPER] = pepper_orders

        conversions = 0
        return result, conversions, json.dumps(trader_state)
