package com.novig.engine;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Resolves a binary market from its fills and a live outcome, computing net P&L
 * per order id. Prices are ticks in [0, MAX_PRICE_TICKS], the implied probability
 * (in cents) that OUTCOME_A wins.
 */
public final class SettlementEngine {

    public enum Outcome { OUTCOME_A_WINS, OUTCOME_B_WINS }

    public static final long MAX_PRICE_TICKS = 100;

    public Map<String, Long> settle(List<Fill> fills, Outcome outcome) {
        Map<String, Long> pnlByOrderId = new HashMap<>();
        long payoutPerUnit = outcome == Outcome.OUTCOME_A_WINS ? MAX_PRICE_TICKS : 0;

        for (Fill fill : fills) {
            long buyerPnl = (payoutPerUnit - fill.priceTicks()) * fill.quantity();
            long sellerPnl = -buyerPnl;

            String buyerOrderId = fill.incomingSide() == Order.Side.BUY ? fill.incomingOrderId() : fill.restingOrderId();
            String sellerOrderId = fill.incomingSide() == Order.Side.SELL ? fill.incomingOrderId() : fill.restingOrderId();

            pnlByOrderId.merge(buyerOrderId, buyerPnl, Long::sum);
            pnlByOrderId.merge(sellerOrderId, sellerPnl, Long::sum);
        }

        return pnlByOrderId;
    }
}
