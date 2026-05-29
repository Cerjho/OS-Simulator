# I/O & Disk Scheduling

Because disk drives have mechanical moving parts (the disk arm and read/write head), the time it takes to seek to a specific cylinder is the dominant performance bottleneck in disk I/O. Disk scheduling algorithms attempt to order pending read/write requests to minimize the total seek distance of the disk arm.

## Algorithms

OS Simulator simulates the following 6 textbook algorithms:

**First-Come, First-Served (FCFS)**
The simplest form of scheduling. Requests are serviced in the exact order they arrive. While inherently fair, it provides the worst performance because the disk arm may swing wildly from one end of the disk to the other.

**Shortest Seek Time First (SSTF)**
Selects the pending request that is closest to the current head position. This significantly reduces total seek distance compared to FCFS. However, it can cause starvation: if a continuous stream of requests arrives near the current head position, requests far away may never be serviced.

**SCAN (The Elevator Algorithm)**
The disk arm starts at one end of the disk and moves toward the other end, servicing requests as it reaches each cylinder. When it hits the end of the disk (cylinder 199), the direction reverses, and it services requests on the way back.

**C-SCAN (Circular SCAN)**
A variant of SCAN designed to provide a more uniform wait time. Like SCAN, it moves the head from one end to the other, servicing requests. However, when it reaches the end, it immediately returns to the beginning of the disk (cylinder 0) *without* servicing any requests on the return trip.

**LOOK**
A smarter version of SCAN. Instead of blindly traveling all the way to cylinder 0 or 199, the arm only goes as far as the final pending request in the current direction. Once there are no more requests ahead, it reverses direction immediately.

**C-LOOK**
A circular version of LOOK. It sweeps in one direction servicing requests until the last request in that direction. Then, it jumps directly back to the lowest pending request and begins sweeping forward again.

## Textbook Benchmark Comparison

Using the standard textbook workload for a disk with 200 cylinders (0-199):
*   **Initial Head Position:** 53
*   **Request Queue:** 98, 183, 37, 122, 14, 124, 65, 67
*   **Initial Direction:** Up (towards 199)

| Algorithm | Seek Sequence | Total Distance |
|-----------|---------------|----------------|
| **FCFS** | 53 → 98 → 183 → 37 → 122 → 14 → 124 → 65 → 67 | 640 |
| **SSTF** | 53 → 65 → 67 → 37 → 14 → 98 → 122 → 124 → 183 | 236 |
| **SCAN** | 53 → 65 → 67 → 98 → 122 → 124 → 183 → 199 → 37 → 14 | 331 |
| **C-SCAN**| 53 → 65 → 67 → 98 → 122 → 124 → 183 → 199 → 0 → 14 → 37 | 382 |
| **LOOK** | 53 → 65 → 67 → 98 → 122 → 124 → 183 → 37 → 14 | 299 |
| **C-LOOK**| 53 → 65 → 67 → 98 → 122 → 124 → 183 → 14 → 37 | 322 |
