# File Systems

The OS Simulator provides a Virtual File System (VFS) abstraction that allows two distinct underlying file system implementations to be tested and compared: FAT (File Allocation Table) and inode-based.

## Comparison

| Feature | FAT | inode |
|---------|-----|-------|
| **Hard links** | No | Yes (via reference counts) |
| **Max file size** | Arbitrarily large (limited by volume size) | Arbitrarily large (via indirect pointers) |
| **Fragmentation** | Higher (blocks scatter, FAT lookups slow down) | Lower (direct/indirect pointers provide fast lookup) |
| **Directory entries**| Store filename + start block | Store filename + inode number |
| **Metadata** | Stored in the directory entry | Stored in the inode |

## FAT (File Allocation Table)

In a FAT filesystem, a central table stores the linked list of blocks for every file. The directory entry only points to the very first block.

When a file is read, the OS must consult the FAT array continuously to find the next block. `FAT_EOF` (End of File) signifies the last block.

### FAT Chain Diagram

```ascii
Directory Entry:
[ "report.txt", size: 3 blocks, start_block: 2 ]

File Allocation Table (FAT Array):
Index | Value
------|---------
  0   | RESERVED
  1   | FREE
  2   | 5       <-- Block 2 points to Block 5
  3   | FREE
  4   | FREE
  5   | 8       <-- Block 5 points to Block 8
  6   | FREE
  7   | FREE
  8   | FAT_EOF <-- Block 8 is the end of the file
```

## Inode Structure

In an inode (index node) filesystem, each file has a dedicated data structure containing its metadata (size, timestamps, link count) and an array of pointers that directly map to data blocks.

The UNIX-style inode implemented in OS Simulator contains direct pointers, a single indirect pointer, and a double indirect pointer to accommodate files of varying sizes efficiently.

### Inode Pointer Structure

```ascii
          ┌───────────────────────────┐
          │ inode 42                  │
          │ ------------------------- │
          │ size: 48 KB               │
          │ type: file                │
          │ links: 1                  │
          │                           │
          │ direct[0]  ─────────► [Data Block 12]
          │ direct[1]  ─────────► [Data Block 34]
          │ ...                       │
          │ direct[11] ─────────► [Data Block 99]
          │                           │
          │ single_indirect ────► [Pointer Block] ─┬─► [Data Block]
          │                                        ├─► [Data Block]
          │                                        └─► [Data Block]
          │                           │
          │ double_indirect ────► [Pointer Block] ─┬─► [Pointer Block] ──► [Data]
          │                                        └─► [Pointer Block] ──► [Data]
          └───────────────────────────┘
```
