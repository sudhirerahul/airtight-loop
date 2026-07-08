package com.novig.engine;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class SettlementEngineTest {

    private static Fill fill(String restingId, Order.Side restingSide,
                              String incomingId, Order.Side incomingSide,
                              long priceTicks, int qty) {
        return new Fill("MKT-1", restingId, restingSide, incomingId, incomingSide, priceTicks, qty, Instant.now());
    }

    @Test
    void buyerProfitsWhenOutcomeAWins() {
        // resting sell at 40 ticks, buyer lifts it for 10 units.
        Fill f = fill("sell-1", Order.Side.SELL, "buy-1", Order.Side.BUY, 40, 10);

        Map<String, Long> pnl = new SettlementEngine().settle(List.of(f), SettlementEngine.Outcome.OUTCOME_A_WINS);

        assertEquals((100 - 40) * 10L, pnl.get("buy-1"));
        assertEquals(-(100 - 40) * 10L, pnl.get("sell-1"));
    }

    @Test
    void sellerProfitsWhenOutcomeBWins() {
        Fill f = fill("sell-1", Order.Side.SELL, "buy-1", Order.Side.BUY, 40, 10);

        Map<String, Long> pnl = new SettlementEngine().settle(List.of(f), SettlementEngine.Outcome.OUTCOME_B_WINS);

        assertEquals(-40L * 10, pnl.get("buy-1"));
        assertEquals(40L * 10, pnl.get("sell-1"));
    }

    @Test
    void netsPnlAcrossMultipleFillsForSameOrder() {
        Fill f1 = fill("sell-1", Order.Side.SELL, "buy-1", Order.Side.BUY, 40, 10);
        Fill f2 = fill("sell-2", Order.Side.SELL, "buy-1", Order.Side.BUY, 60, 5);

        Map<String, Long> pnl = new SettlementEngine().settle(List.of(f1, f2), SettlementEngine.Outcome.OUTCOME_A_WINS);

        long expectedBuyerPnl = (100 - 40) * 10L + (100 - 60) * 5L;
        assertEquals(expectedBuyerPnl, pnl.get("buy-1"));
    }
}
