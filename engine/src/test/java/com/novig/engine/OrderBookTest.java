package com.novig.engine;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class OrderBookTest {

    private static Order order(String id, Order.Side side, long priceTicks, int qty) {
        return new Order(id, "MKT-1", side, priceTicks, qty, Instant.now());
    }

    @Test
    void fullFillMatchesAtRestingPrice() {
        OrderBook book = new OrderBook("MKT-1");
        book.submit(order("sell-1", Order.Side.SELL, 55, 10));

        List<Fill> fills = book.submit(order("buy-1", Order.Side.BUY, 60, 10));

        assertEquals(1, fills.size());
        assertEquals(55, fills.get(0).priceTicks(), "aggressor pays the resting order's price");
        assertEquals(10, fills.get(0).quantity());
        assertEquals(0, book.depthAt(Order.Side.SELL, 55));
    }

    @Test
    void timePriorityWithinSamePriceLevel() {
        OrderBook book = new OrderBook("MKT-1");
        book.submit(order("sell-early", Order.Side.SELL, 50, 5));
        book.submit(order("sell-late", Order.Side.SELL, 50, 5));

        List<Fill> fills = book.submit(order("buy-1", Order.Side.BUY, 50, 5));

        assertEquals(1, fills.size());
        assertEquals("sell-early", fills.get(0).restingOrderId(), "earlier resting order fills first");
    }

    @Test
    void noCrossLeavesBothOrdersResting() {
        OrderBook book = new OrderBook("MKT-1");
        book.submit(order("sell-1", Order.Side.SELL, 60, 10));

        List<Fill> fills = book.submit(order("buy-1", Order.Side.BUY, 55, 10));

        assertTrue(fills.isEmpty());
        assertEquals(10, book.depthAt(Order.Side.SELL, 60));
        assertEquals(10, book.depthAt(Order.Side.BUY, 55));
    }

    @Test
    void partialFillLeavesRemainderRestingInBook() {
        OrderBook book = new OrderBook("MKT-1");
        book.submit(order("sell-1", Order.Side.SELL, 55, 10));

        List<Fill> fills = book.submit(order("buy-1", Order.Side.BUY, 55, 4));

        assertEquals(1, fills.size());
        assertEquals(4, fills.get(0).quantity());
        assertEquals(6, book.depthAt(Order.Side.SELL, 55),
            "resting sell order had 10, 4 were taken, 6 should remain in the book");
    }
}
