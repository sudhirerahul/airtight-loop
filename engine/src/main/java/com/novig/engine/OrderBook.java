package com.novig.engine;

import java.time.Instant;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Deque;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Single-market price-time priority matching engine. Best price matches first;
 * within a price level, earliest-resting order matches first.
 */
public final class OrderBook {
    private final String marketId;
    private final TreeMap<Long, Deque<Order>> buys = new TreeMap<>(Comparator.reverseOrder());
    private final TreeMap<Long, Deque<Order>> sells = new TreeMap<>();

    public OrderBook(String marketId) {
        this.marketId = marketId;
    }

    public String marketId() {
        return marketId;
    }

    public List<Fill> submit(Order incoming) {
        if (!incoming.marketId().equals(marketId)) {
            throw new IllegalArgumentException(
                "order for market " + incoming.marketId() + " submitted to book for " + marketId);
        }

        List<Fill> fills = new ArrayList<>();
        TreeMap<Long, Deque<Order>> opposite = incoming.side() == Order.Side.BUY ? sells : buys;

        while (incoming.remainingQuantity() > 0 && !opposite.isEmpty()) {
            Map.Entry<Long, Deque<Order>> best = opposite.firstEntry();
            long bestPrice = best.getKey();
            if (!crosses(incoming, bestPrice)) {
                break;
            }

            Deque<Order> queue = best.getValue();
            Order resting = queue.peekFirst();

            int tradeQty = Math.min(incoming.remainingQuantity(), resting.remainingQuantity());
            fills.add(new Fill(
                marketId,
                resting.orderId(), resting.side(),
                incoming.orderId(), incoming.side(),
                bestPrice, tradeQty, Instant.now()));

            incoming.reduceRemaining(tradeQty);
            resting.reduceRemaining(tradeQty);

            if (resting.remainingQuantity() == 0) {
                queue.pollFirst();
                if (queue.isEmpty()) {
                    opposite.remove(bestPrice);
                }
            }
        }

        if (incoming.remainingQuantity() > 0) {
            TreeMap<Long, Deque<Order>> own = incoming.side() == Order.Side.BUY ? buys : sells;
            own.computeIfAbsent(incoming.priceTicks(), k -> new ArrayDeque<>()).addLast(incoming);
        }

        return fills;
    }

    public int depthAt(Order.Side side, long priceTicks) {
        TreeMap<Long, Deque<Order>> book = side == Order.Side.BUY ? buys : sells;
        Deque<Order> queue = book.get(priceTicks);
        if (queue == null) {
            return 0;
        }
        return queue.stream().mapToInt(Order::remainingQuantity).sum();
    }

    private boolean crosses(Order incoming, long bestOppositePrice) {
        return incoming.side() == Order.Side.BUY
            ? incoming.priceTicks() >= bestOppositePrice
            : incoming.priceTicks() <= bestOppositePrice;
    }
}
