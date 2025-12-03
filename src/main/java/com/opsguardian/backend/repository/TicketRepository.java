package com.opsguardian.backend.repository;

import com.opsguardian.backend.model.Ticket;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository // Marks this interface as a Spring-managed repository bean
public interface TicketRepository extends JpaRepository<Ticket, Long> {

    // Custom query method that performs a case-insensitive search
    // on both title and description fields.
    // Matches records where either field contains the given keyword.
    List<Ticket> findByTitleContainingIgnoreCaseOrDescriptionContainingIgnoreCase(
            String title,
            String description
    );
}
