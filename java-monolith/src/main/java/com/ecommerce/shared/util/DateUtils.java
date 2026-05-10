package com.ecommerce.shared.util;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;

public class DateUtils {
    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public static String format(LocalDateTime dt) {
        return dt.format(FORMATTER);
    }

    public static LocalDateTime now() {
        return LocalDateTime.now();
    }

    public static boolean isExpired(LocalDateTime expiryDate) {
        return LocalDateTime.now().isAfter(expiryDate);
    }
}
