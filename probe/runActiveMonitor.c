#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

int main(int argc,char *argv[])
{
    char buf[256];
    if (argc != 3) 
    {
        printf("Wrong argument number for %s\n.", argv[0]);
        return 1;
    }
    
    setuid( 0 );
    snprintf(buf, sizeof buf, "%s %s %s", "/usr/bin/python", argv[1], argv[2]);
    system( buf );

    return 0;
}
