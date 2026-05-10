package com.ecommerce.shared.util;

import java.time.LocalDateTime;

public class Logger {
    private String context;

    public Logger(String context) {
        this.context = context;
    }

    public void info(String message) {
        System.out.println("[INFO] [" + DateUtils.format(LocalDateTime.now()) + "] [" + context + "] " + message);
    }

    public void warn(String message) {
        System.out.println("[WARN] [" + DateUtils.format(LocalDateTime.now()) + "] [" + context + "] " + message);
    }

    public void error(String message, Exception e) {
        System.err.println("[ERROR] [" + DateUtils.format(LocalDateTime.now()) + "] [" + context + "] " + message);
        e.printStackTrace();
    }
}
