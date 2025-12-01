package com.opsguardian.backend.model;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.*;

@Entity
@Table(name = "tickets")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@ToString
public class Ticket {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String title;

    @Column(length = 4000)
    private String description;

    private String reporter;
    private String priority;
    private String category;
    private String status;
    private Instant createdAt = Instant.now();
}
