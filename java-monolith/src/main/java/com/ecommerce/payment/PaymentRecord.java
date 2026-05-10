package com.ecommerce.payment;

import java.time.LocalDateTime;

public class PaymentRecord {
    private final Long id;
    private final Long orderId;
    private final double amount;
    private final String status;
    private final LocalDateTime createdAt;

    public PaymentRecord(Long id, Long orderId, double amount, String status, LocalDateTime createdAt) {
        this.id = id;
        this.orderId = orderId;
        this.amount = amount;
        this.status = status;
        this.createdAt = createdAt;
    }

    public Long getId() { return id; }
    public Long getOrderId() { return orderId; }
    public double getAmount() { return amount; }
    public String getStatus() { return status; }
    public LocalDateTime getCreatedAt() { return createdAt; }
}
