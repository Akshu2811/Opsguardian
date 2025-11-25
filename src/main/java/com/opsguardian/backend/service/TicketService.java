package com.opsguardian.backend.service;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.repository.TicketRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class TicketService {
    private final TicketRepository repo;

    public TicketService(TicketRepository repo) {
        this.repo = repo;
    }

    public Ticket create(Ticket t) {
        return repo.save(t);
    }

    public Optional<Ticket> get(Long id) {
        return repo.findById(id);
    }

    public List<Ticket> search(String q) {
        if (q == null || q.isBlank()) {
            return repo.findAll();
        }
        return repo.findByTitleContainingIgnoreCaseOrDescriptionContainingIgnoreCase(q, q);
    }

    public Ticket save(Ticket t) {
        return repo.save(t);
    }
}
