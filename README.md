# Paperfeed

A Python driver for 'Funnyprint' (DOLEWA / Xiqi) mini thermal printers.

This project is currently in early alpha; while I have validated that it works correctly on my printer (DOLEWA D5), try
it on your own devices at your own risk!

## Acknowledgements
Some driver code was adapted from [printer-driver-funnyprint](https://github.com/ValdikSS/printer-driver-funnyprint/)
by ValdikSS, which exposed a CUPS driver for these printers. I heavily re-used their work in replicating the
function of the packets, particularly in relation to the authentication handshake. This work would not have been
possible (or much more challenging) without their contributions to open source!

This project is [licensed](LICENSE) under GPLv2