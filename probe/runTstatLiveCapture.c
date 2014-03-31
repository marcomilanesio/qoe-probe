#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

int main(int argc,char *argv[])
{
    char buf[256];
    if (argc != 4) 
    {
        printf("Wrong argument number for %s\n.", argv[0]);
        return 1;
    }
    
    setuid( 0 );
    snprintf(buf, sizeof buf, "%s %s %s %s", "/usr/bin/python", argv[1], argv[2], argv[3]);
    system( buf );

    return 0;
}
