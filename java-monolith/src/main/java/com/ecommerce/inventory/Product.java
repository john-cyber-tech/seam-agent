package com.ecommerce.inventory;

public class Product {
    private Long id;
    private String name;
    private double price;
    private int stockQuantity;
    private String category;
    private String description;

    public Product() {}

    public Product(Long id, String name, double price, int stockQuantity) {
        this.id = id;
        this.name = name;
        this.price = price;
        this.stockQuantity = stockQuantity;
    }

    public Long getId() { return id; }
    public String getName() { return name; }
    public double getPrice() { return price; }
    public int getStockQuantity() { return stockQuantity; }
    public String getCategory() { return category; }
    public String getDescription() { return description; }

    public void setId(Long id) { this.id = id; }
    public void setName(String name) { this.name = name; }
    public void setPrice(double price) { this.price = price; }
    public void setStockQuantity(int stockQuantity) { this.stockQuantity = stockQuantity; }
    public void setCategory(String category) { this.category = category; }
    public void setDescription(String description) { this.description = description; }
}
