#include <stdio.h>
#include <string.h>
#include "palindrome.h"
#include<sys/socket.h>
#include<arpa/inet.h>	//inet_addr

char *strrev(char *str)
{
      char *p1, *p2;

      if (! str || ! *str)
            return str;
      for (p1 = str, p2 = str + strlen(str) - 1; p2 > p1; ++p1, --p2)
      {
            *p1 ^= *p2;
            *p2 ^= *p1;
            *p1 ^= *p2;
      }
      return str;
}

int is_palidrome(const char *input) {
	int socket_desc;
    struct sockaddr_in server;

	socket_desc = socket(AF_INET , SOCK_STREAM , 0);
    //Create socket
	if (socket_desc == -1)
	{
		printf("Could not create socket\n");
		return 1;
	}

	server.sin_addr.s_addr = inet_addr("127.0.0.1");
	server.sin_family = AF_INET;
	server.sin_port = htons(80);

	//Connect to remote server
	if (connect(socket_desc , (struct sockaddr *)&server , sizeof(server)) < 0)
	{
		perror("could not connect\n");
		return 1;
	}
	printf("connected");

    char newstring[100]; // should be allocated...
    strcpy(newstring, input);
    strrev(newstring);
    return (strcmp(input, newstring) == 0);
}

