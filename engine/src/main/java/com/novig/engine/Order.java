package com.novig.engine;

import java.time.Instant;

public final class Order {
    public enum Side { BUY, SELL }

    private final String orderId;
    private final String marketId;
    private final Side side;
    private final long priceTicks;
    private final Instant timestamp;
    private int remainingQuantity;

    public Order(String orderId, String marketId, Side side, long priceTicks, int quantity, Instant timestamp) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive: " + quantity);
        }
        this.orderId = orderId;
        this.marketId = marketId;
        this.side = side;
        this.priceTicks = priceTicks;
        this.remainingQuantity = quantity;
        this.timestamp = timestamp;
    }

    public String orderId() { return orderId; }
    public String marketId() { return marketId; }
    public Side side() { return side; }
    public long priceTicks() { return priceTicks; }
    public Instant timestamp() { return timestamp; }
    public int remainingQuantity() { return remainingQuantity; }

    public void reduceRemaining(int quantity) {
        if (quantity < 0 || quantity > remainingQuantity) {
            throw new IllegalArgumentException(
                "cannot reduce order " + orderId + " by " + quantity + ", remaining=" + remainingQuantity);
        }
        remainingQuantity -= quantity;
    }

    public boolean isFilled() {
        return remainingQuantity == 0;
    }
}
