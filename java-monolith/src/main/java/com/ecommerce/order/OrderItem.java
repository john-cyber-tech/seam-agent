package com.ecommerce.order;

public class OrderItem {
    private Long id;
    private Long orderId;
    private Long productId;
    private String productName;
    private int quantity;
    private double unitPrice;

    public OrderItem() {}

    public OrderItem(Long productId, String productName, int quantity, double unitPrice) {
        this.productId = productId;
        this.productName = productName;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
    }

    public double getSubtotal() { return quantity * unitPrice; }

    public Long getId() { return id; }
    public Long getOrderId() { return orderId; }
    public Long getProductId() { return productId; }
    public String getProductName() { return productName; }
    public int getQuantity() { return quantity; }
    public double getUnitPrice() { return unitPrice; }

    public void setId(Long id) { this.id = id; }
    public void setOrderId(Long orderId) { this.orderId = orderId; }
}
