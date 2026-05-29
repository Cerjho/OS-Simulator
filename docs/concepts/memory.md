# Memory Management

Memory management in OS Simulator covers two main paradigms: allocating physical frames to processes, and managing virtual memory through demand paging.

## Contiguous Allocation

When a process is loaded, the OS must find a contiguous block of physical frames to satisfy its memory requirement. OS Simulator simulates three standard strategies:

*   **First-Fit:** Scans memory from the beginning and allocates the first block that is large enough. It is generally the fastest algorithm but can lead to external fragmentation early in memory.
*   **Best-Fit:** Scans the entire memory to find the smallest block that is large enough. This minimizes wasted space in the allocated block but tends to leave behind tiny, unusable slivers of memory (severe external fragmentation).
*   **Worst-Fit:** Scans the entire memory to find the largest available block. The idea is that the remaining space after allocation will be large enough to be useful for another process.

*Note:* To combat external fragmentation over time, OS Simulator implements **Memory Compaction**, which physically shifts allocated blocks to coalesce all free space into one large block.

## Virtual Memory & Paging

Virtual memory abstracts physical RAM, giving each process the illusion of a massive, contiguous address space. This is achieved by dividing memory into fixed-size **Pages** (virtual) and **Frames** (physical).

When a process accesses a page not currently in a physical frame, a **Page Fault** occurs. The OS must pause the process, load the required page from disk (swap) into a free frame, and update the page table.

### Translation Lookaside Buffer (TLB)
Because page tables are stored in memory, every memory access would normally require two memory reads (one for the table, one for the data). The TLB is a high-speed hardware cache that stores recent virtual-to-physical translations. A high **TLB Hit Rate** is critical for system performance.

## Page Replacement Algorithms

When memory is full and a page fault occurs, an existing page must be evicted to disk to make room.

| Algorithm | Faults (ref string) | Notes |
|-----------|---------------------|-------|
| **Optimal** | 6 | Replaces the page that will not be used for the longest period of time. Impossible to implement in reality; used as a benchmark. |
| **LRU** | 9 | Least Recently Used. Replaces the page that has not been used for the longest time. Excellent performance, but high overhead to track timestamps. |
| **FIFO** | 10 | First-In, First-Out. Replaces the oldest page in memory regardless of how often it's used. Simple, but prone to poor performance. |
| **Clock** | 9 | An approximation of LRU using a circular queue and a "use bit". Much lower overhead than true LRU. |

*Verified textbook reference string:* `7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3` (3 frames available).

## Bélády's Anomaly

Intuitively, giving a process more physical frames should always decrease or maintain the number of page faults. However, **Bélády's Anomaly** is a phenomenon where increasing the number of page frames actually *increases* the number of page faults.

This anomaly can occur in algorithms like **FIFO**. Because FIFO strictly evicts the oldest page, a heavily used page might be evicted simply because it was loaded first, causing an immediate fault right after.

**LRU and Optimal** are "stack algorithms," meaning the set of pages in memory with `N` frames is always a subset of the pages in memory with `N+1` frames. Therefore, they are mathematically immune to Bélády's Anomaly.
