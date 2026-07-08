package com.novig.replay;

import com.novig.engine.Fill;
import com.novig.engine.Order;
import com.novig.engine.OrderBook;
import com.novig.engine.PriceConverter;
import com.novig.engine.SettlementEngine;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Replays a captured odds+scores window through the engine (OrderBook +
 * SettlementEngine) and emits a per-market P&L summary as JSON on stdout.
 *
 * Odds -> orders: The Odds API's h2h market has no order-size field, so rather
 * than invent one, each bookmaker's home-team moneyline quote at a point in time
 * is treated as a synthetic two-sided quote (SELL above, BUY below) around its
 * own implied probability that the home team wins. Divergent bookmaker lines are
 * what generate fills here -- one bookmaker's synthetic bid crossing another's
 * synthetic ask -- which mirrors real line-shopping/arbitrage dynamics instead of
 * a fabricated size field.
 *
 * CLI: java -cp <classpath> com.novig.replay.ReplayHarness <odds.ndjson> <scores.ndjson>
 */
public final class ReplayHarness {

    static final long SPREAD_HALF_TICKS = 1L;
    static final int SYNTHETIC_QUANTITY = 10;

    public static final class MarketResult {
        public final Map<String, Long> pnlByOrder;
        public final int fillCount;

        public MarketResult(Map<String, Long> pnlByOrder, int fillCount) {
            this.pnlByOrder = pnlByOrder;
            this.fillCount = fillCount;
        }
    }

    public static final class ReplaySummary {
        public final Map<String, MarketResult> markets;
        public final long wallClockMillis;

        public ReplaySummary(Map<String, MarketResult> markets, long wallClockMillis) {
            this.markets = markets;
            this.wallClockMillis = wallClockMillis;
        }
    }

    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("usage: ReplayHarness <odds.ndjson> <scores.ndjson>");
            System.exit(2);
        }
        ReplaySummary summary = replay(Path.of(args[0]), Path.of(args[1]));
        System.out.println(toJson(summary));
    }

    public static ReplaySummary replay(Path oddsFile, Path scoresFile) {
        long start = System.currentTimeMillis();

        List<Map<String, String>> oddsRows = readRows(oddsFile);
        List<Map<String, String>> scoreRows = readRows(scoresFile);

        Map<String, SettlementEngine.Outcome> outcomeByEvent = resolveFinalOutcomes(scoreRows);

        Map<String, List<Map<String, String>>> oddsByEvent = new LinkedHashMap<>();
        for (Map<String, String> row : oddsRows) {
            oddsByEvent.computeIfAbsent(row.get("event_id"), k -> new ArrayList<>()).add(row);
        }

        Map<String, MarketResult> markets = new TreeMap<>();
        SettlementEngine settlementEngine = new SettlementEngine();

        for (Map.Entry<String, List<Map<String, String>>> entry : oddsByEvent.entrySet()) {
            String eventId = entry.getKey();
            List<Fill> fills = replayMarket(eventId, entry.getValue());

            SettlementEngine.Outcome outcome = outcomeByEvent.get(eventId);
            Map<String, Long> pnl = outcome != null
                ? new TreeMap<>(settlementEngine.settle(fills, outcome))
                : new TreeMap<>();

            markets.put(eventId, new MarketResult(pnl, fills.size()));
        }

        long elapsed = System.currentTimeMillis() - start;
        return new ReplaySummary(markets, elapsed);
    }

    private static List<Fill> replayMarket(String eventId, List<Map<String, String>> rows) {
        List<Map<String, String>> homeTicks = new ArrayList<>();
        for (Map<String, String> row : rows) {
            if (row.get("outcome_name") != null && row.get("outcome_name").equals(row.get("home_team"))) {
                homeTicks.add(row);
            }
        }
        homeTicks.sort(Comparator.comparing(ReplayHarness::tickTimestamp));

        OrderBook book = new OrderBook(eventId);
        List<Fill> fills = new ArrayList<>();
        int counter = 0;

        for (Map<String, String> tick : homeTicks) {
            long homePriceTicks = PriceConverter.americanOddsToPriceTicks(Integer.parseInt(tick.get("price_american")));
            long sellPrice = clamp(homePriceTicks + SPREAD_HALF_TICKS);
            long buyPrice = clamp(homePriceTicks - SPREAD_HALF_TICKS);
            String bookmaker = tick.get("bookmaker");
            Instant ts = tickTimestamp(tick);
            counter++;

            fills.addAll(book.submit(new Order(
                bookmaker + "-" + counter + "-sell", eventId, Order.Side.SELL, sellPrice, SYNTHETIC_QUANTITY, ts)));
            fills.addAll(book.submit(new Order(
                bookmaker + "-" + counter + "-buy", eventId, Order.Side.BUY, buyPrice, SYNTHETIC_QUANTITY, ts)));
        }

        return fills;
    }

    private static Map<String, SettlementEngine.Outcome> resolveFinalOutcomes(List<Map<String, String>> scoreRows) {
        Map<String, SettlementEngine.Outcome> outcomes = new LinkedHashMap<>();
        for (Map<String, String> row : scoreRows) {
            if (!"final".equals(row.get("status"))) {
                continue;
            }
            String winner = row.get("winner");
            if ("home".equals(winner)) {
                outcomes.put(row.get("event_id"), SettlementEngine.Outcome.OUTCOME_A_WINS);
            } else if ("away".equals(winner)) {
                outcomes.put(row.get("event_id"), SettlementEngine.Outcome.OUTCOME_B_WINS);
            }
        }
        return outcomes;
    }

    private static long clamp(long priceTicks) {
        return Math.max(0, Math.min(SettlementEngine.MAX_PRICE_TICKS, priceTicks));
    }

    private static Instant tickTimestamp(Map<String, String> row) {
        String raw = row.get("last_update");
        if (raw == null || raw.isBlank()) {
            raw = row.get("captured_at");
        }
        try {
            return OffsetDateTime.parse(raw).toInstant();
        } catch (DateTimeParseException | NullPointerException e) {
            return Instant.EPOCH;
        }
    }

    private static List<Map<String, String>> readRows(Path file) {
        List<Map<String, String>> rows = new ArrayList<>();
        if (!Files.exists(file)) {
            return rows;
        }
        try {
            for (String line : Files.readAllLines(file)) {
                if (line.isBlank()) {
                    continue;
                }
                rows.add(NdjsonReader.parseRow(line));
            }
        } catch (IOException e) {
            throw new UncheckedIOException(e);
        }
        return rows;
    }

    static String toJson(ReplaySummary summary) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"markets\":{");
        boolean firstMarket = true;
        for (Map.Entry<String, MarketResult> marketEntry : summary.markets.entrySet()) {
            if (!firstMarket) {
                sb.append(',');
            }
            firstMarket = false;
            sb.append('"').append(escape(marketEntry.getKey())).append("\":{");
            sb.append("\"pnl_by_order\":{");
            boolean firstOrder = true;
            for (Map.Entry<String, Long> pnlEntry : marketEntry.getValue().pnlByOrder.entrySet()) {
                if (!firstOrder) {
                    sb.append(',');
                }
                firstOrder = false;
                sb.append('"').append(escape(pnlEntry.getKey())).append("\":").append(pnlEntry.getValue());
            }
            sb.append("},\"fill_count\":").append(marketEntry.getValue().fillCount);
            sb.append('}');
        }
        sb.append("},\"wall_clock_millis\":").append(summary.wallClockMillis).append('}');
        return sb.toString();
    }

    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"");
    }
}
