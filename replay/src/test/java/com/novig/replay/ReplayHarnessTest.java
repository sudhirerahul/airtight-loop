package com.novig.replay;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ReplayHarnessTest {

    /**
     * Two bookmakers quote divergent lines for the same market: A implies a 60%
     * home-win probability, B (quoting later) implies 80%. B's synthetic BUY
     * crosses A's resting synthetic SELL at A's price (61), for exactly the
     * synthetic quantity -- a full fill, so this case is unaffected by the
     * separate, still-unmerged Day-1 partial-fill bug in OrderBook.
     */
    @Test
    void divergentBookmakerLinesProduceAFillAndCorrectSettlement(@TempDir Path tempDir) throws IOException {
        Path odds = tempDir.resolve("odds.ndjson");
        Files.writeString(odds, String.join("\n",
            "{\"event_id\": \"TEST-1\", \"home_team\": \"Home Team\", \"outcome_name\": \"Home Team\", \"bookmaker\": \"A\", \"price_american\": -150, \"last_update\": \"2026-01-01T00:00:00Z\"}",
            "{\"event_id\": \"TEST-1\", \"home_team\": \"Home Team\", \"outcome_name\": \"Home Team\", \"bookmaker\": \"B\", \"price_american\": -400, \"last_update\": \"2026-01-01T00:10:00Z\"}"
        ) + "\n");

        Path scores = tempDir.resolve("scores.ndjson");
        Files.writeString(scores, "{\"event_id\": \"TEST-1\", \"status\": \"final\", \"winner\": \"home\"}\n");

        ReplayHarness.ReplaySummary summary = ReplayHarness.replay(odds, scores);

        ReplayHarness.MarketResult market = summary.markets.get("TEST-1");
        assertEquals(1, market.fillCount);
        assertEquals(390L, market.pnlByOrder.get("B-2-buy"));
        assertEquals(-390L, market.pnlByOrder.get("A-1-sell"));
    }

    @Test
    void unsettledMarketWithNoFinalScoreHasEmptyPnl(@TempDir Path tempDir) throws IOException {
        Path odds = tempDir.resolve("odds.ndjson");
        Files.writeString(odds,
            "{\"event_id\": \"TEST-2\", \"home_team\": \"Home Team\", \"outcome_name\": \"Home Team\", \"bookmaker\": \"A\", \"price_american\": -150, \"last_update\": \"2026-01-01T00:00:00Z\"}\n");

        Path scores = tempDir.resolve("scores.ndjson");
        Files.writeString(scores, "{\"event_id\": \"TEST-2\", \"status\": \"in_progress\", \"winner\": null}\n");

        ReplayHarness.ReplaySummary summary = ReplayHarness.replay(odds, scores);

        assertTrue(summary.markets.get("TEST-2").pnlByOrder.isEmpty());
    }

    @Test
    void replaysFixtureWindowAgainstRealSettledGame() {
        Path odds = Path.of("testdata/sample_window/odds.ndjson");
        Path scores = Path.of("testdata/sample_window/scores.ndjson");

        ReplayHarness.ReplaySummary summary = ReplayHarness.replay(odds, scores);

        ReplayHarness.MarketResult market = summary.markets.get("401859967");
        assertTrue(market.fillCount > 0, "divergent bookmaker lines in the fixture should cross and fill");
        assertFalse(market.pnlByOrder.isEmpty(), "the real captured game resolved final, so P&L should settle");

        long netPnl = market.pnlByOrder.values().stream().mapToLong(Long::longValue).sum();
        assertEquals(0L, netPnl, "settlement is zero-sum across counterparties");
    }

    @Test
    void jsonOutputIsWellFormedAndDeterministicallyOrdered() {
        Map<String, Long> pnl = Map.of("z-order", 10L, "a-order", -10L);
        ReplayHarness.MarketResult market = new ReplayHarness.MarketResult(new java.util.TreeMap<>(pnl), 3);
        ReplayHarness.ReplaySummary summary = new ReplayHarness.ReplaySummary(
            new java.util.TreeMap<>(Map.of("EVT-1", market)), 42L);

        String json = ReplayHarness.toJson(summary);

        assertTrue(json.contains("\"a-order\":-10"));
        assertTrue(json.indexOf("a-order") < json.indexOf("z-order"), "keys are sorted for stable diffing");
        assertTrue(json.contains("\"fill_count\":3"));
        assertTrue(json.contains("\"wall_clock_millis\":42"));
    }
}
