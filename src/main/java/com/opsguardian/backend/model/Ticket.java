package com.opsguardian.backend.model;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.*;


import java.time.Instant;

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

    private String priority; // P0, P1, P2, P3

    private String category; // Database, Network, Application, Access, Security, Other

    private String status; // OPEN, TRIAGED, ASSIGNED, RESOLVED

    private Instant createdAt = Instant.now();
}