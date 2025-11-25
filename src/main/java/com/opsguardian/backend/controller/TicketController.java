package com.opsguardian.backend.controller;

import com.opsguardian.backend.model.Ticket;
import com.opsguardian.backend.service.TicketService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/tickets")
public class TicketController {

    private final TicketService service;

    public TicketController(TicketService service) {
        this.service = service;
    }

    @GetMapping
    public ResponseEntity<List<Ticket>> list(@RequestParam(required = false) String query) {
        List<Ticket> tickets = service.search(query);
        return ResponseEntity.ok(tickets);
    }

    @PostMapping
    public ResponseEntity<Ticket> create(@RequestBody Ticket ticket) {
        Ticket created = service.create(ticket);
        return ResponseEntity.status(201).body(created);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Ticket> get(@PathVariable Long id) {
        return service.get(id)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    // placeholder: add suggestions (agent -> store suggestions)
    @PostMapping("/{id}/suggestions")
    public ResponseEntity<?> addSuggestions(@PathVariable Long id, @RequestBody Map<String, Object> suggestions) {
        // For MVP, just log and return 200. Later persist suggestions table.
        System.out.println("Suggestions for ticket " + id + ": " + suggestions);
        return ResponseEntity.ok(Map.of("status", "ok"));
    }

    // placeholder: apply a suggestion (simulate)
    @PostMapping("/{id}/apply-suggestion")
    public ResponseEntity<?> applySuggestion(@PathVariable Long id, @RequestBody Map<String, Object> req) {
        System.out.println("Apply suggestion for ticket " + id + ": " + req);
        return ResponseEntity.ok(Map.of("status", "applied"));
    }

    // assign ticket to team
    @PostMapping("/{id}/assign")
    public ResponseEntity<?> assign(@PathVariable Long id, @RequestBody Map<String, Object> assignment) {
        service.get(id).ifPresent(t -> {
            Object team = assignment.get("team");
            t.setStatus("ASSIGNED");
            service.save(t);
            System.out.println("Assigned ticket " + id + " to " + team);
        });
        return ResponseEntity.ok(Map.of("status", "assigned"));
    }
}
