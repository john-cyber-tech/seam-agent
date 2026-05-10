package com.ecommerce.order;

import java.time.LocalDateTime;
import java.util.List;

public class Order {
    private Long id;
    private Long userId;
    private List<OrderItem> items;
    private String status;
    private double totalAmount;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private String shippingAddress;

    public Order() {}

    public Order(Long userId, List<OrderItem> items, String shippingAddress) {
        this.userId = userId;
        this.items = items;
        this.shippingAddress = shippingAddress;
        this.status = "PENDING";
        this.createdAt = LocalDateTime.now();
        this.updatedAt = LocalDateTime.now();
        this.totalAmount = items.stream().mapToDouble(OrderItem::getSubtotal).sum();
    }

    public Long getId() { return id; }
    public Long getUserId() { return userId; }
    public List<OrderItem> getItems() { return items; }
    public String getStatus() { return status; }
    public double getTotalAmount() { return totalAmount; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public String getShippingAddress() { return shippingAddress; }

    public void setId(Long id) { this.id = id; }
    public void setStatus(String status) { this.status = status; this.updatedAt = LocalDateTime.now(); }
    public void setTotalAmount(double totalAmount) { this.totalAmount = totalAmount; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
