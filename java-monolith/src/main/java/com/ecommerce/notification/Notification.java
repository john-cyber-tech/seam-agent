package com.ecommerce.notification;

import java.time.LocalDateTime;

public class Notification {
    private Long id;
    private Long userId;
    private String type;
    private String subject;
    private String body;
    private LocalDateTime sentAt;
    private boolean delivered;

    public Notification() {}

    public Notification(Long userId, String type, String subject, String body) {
        this.userId = userId;
        this.type = type;
        this.subject = subject;
        this.body = body;
        this.sentAt = LocalDateTime.now();
        this.delivered = false;
    }

    public Long getId() { return id; }
    public Long getUserId() { return userId; }
    public String getType() { return type; }
    public String getSubject() { return subject; }
    public String getBody() { return body; }
    public LocalDateTime getSentAt() { return sentAt; }
    public boolean isDelivered() { return delivered; }

    public void setId(Long id) { this.id = id; }
    public void setDelivered(boolean delivered) { this.delivered = delivered; }
}
