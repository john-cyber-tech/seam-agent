package com.ecommerce.order;

import com.ecommerce.inventory.InventoryService;
import com.ecommerce.notification.NotificationService;
import com.ecommerce.payment.PaymentService;
import com.ecommerce.shared.util.Logger;
import com.ecommerce.user.UserService;

import java.util.List;
import java.util.Optional;

public class OrderService {
    private final OrderRepository orderRepository = new OrderRepository();
    private final InventoryService inventoryService = new InventoryService();
    private final PaymentService paymentService = new PaymentService();
    private final NotificationService notificationService = new NotificationService();
    private final UserService userService = new UserService();
    private final Logger logger = new Logger("OrderService");

    public Order placeOrder(Long userId, List<OrderItem> items, String shippingAddress, String paymentToken) {
        userService.getUserById(userId)
            .orElseThrow(() -> new RuntimeException("User not found: " + userId));

        for (OrderItem item : items) {
            if (!inventoryService.isAvailable(item.getProductId(), item.getQuantity())) {
                throw new RuntimeException("Insufficient stock for product: " + item.getProductId());
            }
        }

        Order order = new Order(userId, items, shippingAddress);
        orderRepository.save(order);

        boolean paid = paymentService.processPayment(order.getId(), order.getTotalAmount(), paymentToken);
        if (!paid) {
            orderRepository.updateStatus(order.getId(), "PAYMENT_FAILED");
            throw new RuntimeException("Payment failed for order: " + order.getId());
        }

        for (OrderItem item : items) {
            inventoryService.reserve(item.getProductId(), item.getQuantity());
        }

        orderRepository.updateStatus(order.getId(), "CONFIRMED");
        notificationService.sendOrderConfirmation(order);
        logger.info("Order placed successfully: " + order.getId());
        return order;
    }

    public void cancelOrder(Long orderId) {
        orderRepository.findById(orderId).ifPresent(order -> {
            paymentService.refund(orderId, order.getTotalAmount());
            for (OrderItem item : order.getItems()) {
                inventoryService.release(item.getProductId(), item.getQuantity());
            }
            orderRepository.updateStatus(orderId, "CANCELLED");
            notificationService.sendOrderCancellation(order);
            logger.info("Order cancelled: " + orderId);
        });
    }

    public Optional<Order> getOrder(Long orderId) {
        return orderRepository.findById(orderId);
    }

    public List<Order> getUserOrders(Long userId) {
        return orderRepository.findByUserId(userId);
    }

    public List<Order> getPendingOrders() {
        return orderRepository.findByStatus("PENDING");
    }
}
