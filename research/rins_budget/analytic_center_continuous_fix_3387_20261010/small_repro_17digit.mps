NAME SMALL_REPRO
OBJSENSE
 MAX
ROWS
 N OBJ
 E k_balance
 E y_balance
 L gate
 E subset
COLUMNS
    g OBJ 1
    g k_balance -1.9999999999999999e-06
    g gate 1
    f k_balance -1
    f y_balance -1
    r k_balance 1
    r y_balance 1
    y y_balance -1
    MARK0000 'MARKER' 'INTORG'
    v gate -1
    v subset -1470
    z0 subset 525
    z1 subset 560
    z2 subset 779
    z3 subset 955
    z4 subset 131
    z5 subset 229
    MARK0001 'MARKER' 'INTEND'
RHS
    RHS1 k_balance 0
    RHS1 y_balance 0
    RHS1 gate 0
    RHS1 subset 0
BOUNDS
 LO BND g 0
 UP BND g 1
 LO BND f 0
 UP BND f 1000
 LO BND r 0
 UP BND r 1000
 LO BND y 0
 UP BND y 1000
 BV BND v
 BV BND z0
 BV BND z1
 BV BND z2
 BV BND z3
 BV BND z4
 BV BND z5
ENDATA
