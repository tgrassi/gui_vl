#include <stdio.h>
#include <stdlib.h>

#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/types.h>
#include <unistd.h>
#include <errno.h>

/* Open a socket and return handle */
int create_socket(const char *hostname, uint16_t  port)
{
  printf("Try to connect to %s \n", hostname);
  int sockfd = 0;
  struct sockaddr_in serv_addr;

  /* create socket */
  sockfd = socket( AF_INET, SOCK_STREAM, 0);
  if (sockfd < 0)
    {
      printf("\n Error: Could not create a socket \n");
      return 1;
    }
  /* Connect to server */
  serv_addr.sin_family = AF_INET;
  serv_addr.sin_port = htons(port);
  serv_addr.sin_addr.s_addr = inet_addr(hostname);
  
  printf("connect to socket\n");
  if(connect(sockfd, (struct sockaddr *)&serv_addr, sizeof(serv_addr))<0)
    {
      printf("\n Error : Connect Failed \n");
      return 1;
    }
  printf("Socket: %d\n", sockfd);
  return sockfd;
    
}

int close_socket(int sockfd)
{
  int retValue;

  if (retValue = close(sockfd)<0)
    {
      perror("Close failed: ");
    }
  return retValue;
}

void write_to_server (int fd, const char *message)
{
  int nbytes;
  printf("Send %s to server \n", message);
  //nbytes = write (fd, message, strlen (message) + 1);
  nbytes = write(fd, "CURVESTREAM?\n", 13);
  if (nbytes < 0)
    {
      perror ("write");
      exit (EXIT_FAILURE);
    }
}

int process_buffer(int n, char *pBuff, int32_t **pos_dataarray, int32_t **pos_ptr_dataarray, int * datalength, int *num_scans)
{
  int i;
  //int datalength = 0;
  int lencounter = 0;
  int len_missing = 0; // Number of remaining positions to fill within the dataarray
  char clencounter[2] = "xx"; // The first byte contains curve length as hex, second byte terminates the hex for strtol function
  unsigned char cdatalength[4];
  int32_t *dataarray;
  int32_t *ptr_dataarray;

  char *ptr_pBuff; // pointer to current position in pBuff

  /* set pointers to the addresses of dataarray */
  dataarray = *pos_dataarray;
  ptr_dataarray = *pos_ptr_dataarray;
  
  /* set the pointer to first byte of the buffer */
  ptr_pBuff = pBuff;

  /* process the buffer until the end of the buffer is reached */
  do 
    {
      /* check if buffer is at the beginning of a new curve 
	 and if so then start a new record entry. Otherwise
	 continue last curve */
      if ( ((ptr_pBuff)[0] !='#') && (*num_scans == 0) && (dataarray == ptr_dataarray))
	{
	  printf("\rSkip first buffer, because it does not start with # ");
	  break;
	}

      if ((ptr_pBuff)[0] == '#') 
	{	   
	  ptr_pBuff++;
	  /* copy byte which contains the length of datalength as hex number.
	     For strtol it is important that second byte is not [0-9][a-f] */
	  strncpy(clencounter, ptr_pBuff, 1); 
	  lencounter = (int)strtol(clencounter, NULL, 16);

	  ptr_pBuff++;
	  strncpy(cdatalength, ptr_pBuff, lencounter); 
	  sscanf(cdatalength, "%d", datalength);

	  ptr_pBuff = ptr_pBuff + lencounter;
/* 	  	  printf("# of scan: %d \n", *num_scans); */
/* 	  	  printf("n: %d \n", n); */
	  /* 	  printf("buffer: %s \n", recvBuff); */
	  /* 	  printf("len-counter: %d \n", lencounter); */
	  printf("\rStart scan %d with datalength: %d", *num_scans, *datalength);
	  
	  if (*num_scans == 0) {
	    // curvebuffer=(unsigned char *)malloc(datalength * sizeof(unsigned char));
	    dataarray = (int32_t *)malloc(*datalength * sizeof(int32_t));
	    ptr_dataarray = dataarray;
	  }
	}
      len_missing = *datalength + dataarray - ptr_dataarray;
      /* Read the data from buffer and store it in dataarray */
      if (n > len_missing)
	{
	  /* buffer contains completely the data, so loop until all data is processed */
//	  for (i = 0; i < len_missing; i++) {
	  while (*datalength > ptr_dataarray - dataarray) {
	    ptr_dataarray[0] += (int) ptr_pBuff[0];
	    ptr_pBuff++;
	    ptr_dataarray++;
	  }
	  /* to additional bytes are added to curve data (presumably ';\n' */
	  //ptr_pBuff=ptr_pBuff + 2;
/* 	  printf("Curve complete \n"); */
//	  printf("last datapoints %x \n", ptr_pBuff[0]);
//	  ptr_pBuff++;
	  if (*(ptr_pBuff++) == 59 && *(ptr_pBuff++) == 10) 
	    {
/* 	      printf("Curve ended correctly \n"); */
/* 	      printf("Buffer read %d \n", ptr_pBuff-pBuff); */
/* 	      printf("Data written %d \n", ptr_dataarray - dataarray); */
	    }
	  /* set the dataarray pointer to the first element */
	  ptr_dataarray = dataarray;
	  (*num_scans)++;
	}
      else 
	{
/* 	  printf("Read until end of buffer \n"); */
	  /* Read datapoints until the end of the buffer */
//	  for (i = 0; i < n + pBuff - ptr_pBuff; i++) {
	  while ( ptr_pBuff - pBuff < n) {
	    ptr_dataarray[0] += (int) ptr_pBuff[0];
	    ptr_pBuff++;
	    ptr_dataarray++;
	  }
/* 	  printf("Buffer read %d \n", ptr_pBuff-pBuff); */
/* 	  printf("Data written %d \n", ptr_dataarray - dataarray); */
	}
    } while (ptr_pBuff - pBuff < n);

  /* set pointers to the addresses */
  *pos_dataarray = dataarray;
  *pos_ptr_dataarray = ptr_dataarray;

  return 0;
}

int read_from_server(int fd)
{

  int datalength = 0;

  int i;
  int n = 0;
  int num_scans = 0;
  int flag_write = 1; // determines if curve shall be written or skipped 
  char recvBuff[8192];
  int buffer_read_count = 0;

  int32_t * dataarray;
  int32_t * ptr_dataarray = dataarray;
  
  /* position where the pointers are stored */
  int32_t **pos_dataarray = &dataarray;
  int32_t **pos_ptr_dataarray = &ptr_dataarray;

  memset(recvBuff, '0' ,sizeof(recvBuff));

  /* open file where the averages are stored */
  FILE *ifp;
  char *mode = "w";
  ifp = fopen("cdump.dat", mode);

  printf("Receive data from server: \n");

  /* read the buffer until no data is retrieved anymore or an error has occured */
  while((n = read(fd, recvBuff, sizeof(recvBuff)-1)) > 0)
    { 
      //printf("Buffer read %d times\n", buffer_read_count);
      buffer_read_count++;

/*       printf("Process buffer size %d \n", n); */
      /* parse and read the buffer and add scan to dataarray which contains the sum of all scans */
      process_buffer(n, recvBuff, pos_dataarray, pos_ptr_dataarray, &datalength, &num_scans);
      
      //printf("# scans: %d, flag: %d\n", num_scans, flag_write); 
      /* write averages to file every 100 scans */
      if ((num_scans > 0) && (num_scans%10 == 0) && (flag_write == 1))
	{
/* 	  printf("\nDatalength: %d \n", datalength); */
	  printf("\rStore average over %d scans.                          \n", num_scans);
	  for (i = 0; i < datalength; i++) {
	    fprintf(ifp, "%lf ", (double)dataarray[i] ); // num_scans);
	  }
	  fprintf(ifp, "\n");
	  flag_write = 0;
	}
      else if (num_scans%10 > 0)
	{
	  flag_write = 1;
	}

    }
  
  if( n < 0)
    {
      //printf("\n Read Error \n");
      perror("Error printed by perror");
    }
  
  return 0;
}

void write_buffer (int fd, const char *message)
{
  int nbytes;
  printf("Send %s to server (len: %d)\n", message, strlen(message));
  nbytes = send (fd, message, strlen (message), 0 );
  //  nbytes = write(fd, "*IDN?\n", 6);
  if (nbytes < 0)
    {
      perror ("write");
      exit (EXIT_FAILURE);
    }
}

int read_buffer(int fd)
{
  int n = 0;
  char recvBuff[8192];

  memset(recvBuff, '0' ,sizeof(recvBuff));
  printf("Receive data from server: \n");

  /* read the buffer until no data is retrieved anymore or an error has occured */
  if((n = recv(fd, recvBuff, sizeof(recvBuff)-1,0)) > 0)
    { 
      // Add zero Byte to determine the end of the string which was written into the buffer
      recvBuff[n] = 0; 
      printf("Buffer: \n%s", recvBuff);
    }
  else
    {
      recvBuff[0] = 0;
    }
  
  if( n < 0)
    {
      //printf("\n Read Error \n");
      perror("Error printed by perror");
    }
  return 0;
}

int get_buffer(int fd, char *recvBuff, int recvBuff_size)
{
  int n = 0;

  memset(recvBuff, '0' ,recvBuff_size);
/*   printf("Receive data from server: \n"); */

  /* read the buffer until no data is retrieved anymore or an error has occured */
  if((n = recv(fd, recvBuff, recvBuff_size-1,0)) > 0)
    { 
      // Add zero Byte to determine the end of the string which was written into the buffer
      recvBuff[n] = 0; 
/*       printf("Buffer: \n%s", recvBuff); */
    }
  else
    {
      recvBuff[0] = 0;
    }
  
  if( n < 0)
    {
      //printf("\n Read Error \n");
      perror("Error printed by perror");
    }
  return n;
}

int main()
{
  FILE *ifp;
  char *mode = "r";
  unsigned char datapoint;
  int i;
  int num_scans = 0;
  unsigned char header[1];
  unsigned char footer[2];
  unsigned char clencounter;
  unsigned char cdatalength[4];

  unsigned char *curvebuffer;

  int lencounter;
  int datalength;

  int32_t * dataarray;
  int test, sockfd;
  char *host_ip = "192.168.23.30";

  sockfd = create_socket(host_ip, 4000);
  write_buffer(sockfd, "*IDN?\n");
  read_buffer(sockfd);
  write_buffer(sockfd, "CURVESTREAM?\n");
  test = read_from_server(sockfd);
  close(sockfd);

/*   ifp = fopen("testdump.dat", mode); */
/*   //fscanf(ifp, "%1s%1d", header, &lencounter ); */

/*   while(!feof(ifp)) { */

/*     /\* Read curve header data and determine number of datapoints *\/ */
/*     fread(&header, sizeof(unsigned char), 1, ifp); */
/*     fread(&clencounter, sizeof(unsigned char), 1, ifp); */
/*     sscanf(&clencounter, "%d", &lencounter); */

/*     fread(&cdatalength, sizeof(unsigned char), lencounter, ifp); */
/*     sscanf(cdatalength, "%d", &datalength); */

/*     //printf("header %s \n", header); */
/*     //printf("counter length: %d \n", lencounter); */
/*     //printf("data length: %d \n", datalength); */
  
/*     if (num_scans == 0) { */
/*       curvebuffer=(unsigned char *)malloc(datalength * sizeof(unsigned char)); */
/*       dataarray = (int32_t *)malloc(datalength * sizeof(int32_t)); */
/*     } */
/*     fread(curvebuffer, sizeof(unsigned char), datalength, ifp); */
 
/*     /\* Read datapoints *\/ */
/*     for (i = 0; i < datalength; i++) { */
/*       // fread(&datapoint, 1, 1, ifp); */
/*       dataarray[i] += (int) curvebuffer[i]; */
/*       //printf("%d ", curvebuffer[i]); //datapoint); */
/*     } */
/*     fread(&footer, sizeof(unsigned char), 2, ifp); */
/*     num_scans++; */
/*   } */
/*   fclose(ifp); */

/*   printf("\nNumber of Scans: %d \n", num_scans); */
/*   printf("Sum over all scans: \n"); */
/*   for (i = 0; i < datalength; i++) { */
/*     printf("%lf ", (double)dataarray[i] / num_scans); */
/*   } */
  return 0;
}
