int putchar(int);

int main(void)
{
    int z;

    for (z = 0; z < 90; z++) {
        int col = z % 9;
        int row = z / 9;
        int inside = (col + row > 3 &&
                      col + row < 14 &&
                      row < col + 6 &&
                      row > col - 5);

        putchar(inside ? '*' : ' ');

        if (col == 8)
            putchar('\n');
    }
    putchar('\n');

    return 0;
}
