package com.ecommerce.notification;

import com.ecommerce.order.Order;
import com.ecommerce.shared.model.User;
import com.ecommerce.shared.util.EmailSender;
import com.ecommerce.shared.util.Logger;

import javax.mail.MessagingException;

public class NotificationService {
    private final Logger logger = new Logger("NotificationService");
    private final NotificationRepository notificationRepository = new NotificationRepository();

    public void sendWelcomeEmail(User user) {
        String subject = "Welcome to ECommerce!";
        String body = "Hi " + user.getUsername() + ",\n\nWelcome! Your account has been created.";
        send(user.getEmail(), subject, body, "WELCOME", user.getId());
    }

    public void sendAccountDeactivationEmail(User user) {
        String subject = "Account Deactivated";
        String body = "Hi " + user.getUsername() + ",\n\nYour account has been deactivated.";
        send(user.getEmail(), subject, body, "DEACTIVATION", user.getId());
    }

    public void sendOrderConfirmation(Order order) {
        String subject = "Order Confirmed #" + order.getId();
        String body = "Your order #" + order.getId() + " has been confirmed.\nTotal: $" + order.getTotalAmount();
        send(resolveUserEmail(order.getUserId()), subject, body, "ORDER_CONFIRMATION", order.getUserId());
    }

    public void sendOrderCancellation(Order order) {
        String subject = "Order Cancelled #" + order.getId();
        String body = "Your order #" + order.getId() + " has been cancelled.";
        send(resolveUserEmail(order.getUserId()), subject, body, "ORDER_CANCELLATION", order.getUserId());
    }

    public void sendPaymentFailureAlert(Long userId, Long orderId) {
        String subject = "Payment Failed for Order #" + orderId;
        String body = "Unfortunately, your payment for order #" + orderId + " failed. Please retry.";
        send(resolveUserEmail(userId), subject, body, "PAYMENT_FAILURE", userId);
    }

    public void sendLowStockAlert(String adminEmail, Long productId, int remaining) {
        String subject = "Low Stock Alert: Product #" + productId;
        String body = "Product #" + productId + " has only " + remaining + " units remaining.";
        send(adminEmail, subject, body, "LOW_STOCK", null);
    }

    private void send(String to, String subject, String body, String type, Long userId) {
        try {
            EmailSender.send(to, subject, body);
            notificationRepository.save(new Notification(userId, type, subject, body));
            logger.info("Sent " + type + " notification to: " + to);
        } catch (MessagingException e) {
            logger.error("Failed to send notification to: " + to, e);
        }
    }

    private String resolveUserEmail(Long userId) {
        // In a real system this would call UserRepository directly — intentional coupling
        return "user-" + userId + "@ecommerce.com";
    }
}
