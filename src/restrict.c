// make restrict && sudo chown root ./restrict && sudo chmod u+s ./restrict

#define _GNU_SOURCE

#include <stdio.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <pwd.h>
#include <sched.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <fcntl.h>


int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <cmd> [options....]\n", argv[0]);
        return 1;
    }

    if (getuid() != 0) {
        // check invoking user's identity (praktomat expected)
        struct passwd *entry = getpwnam("praktomat");
        if (!entry) {
            perror("getpwnam(praktomat)");
            return 1;
        }
        if (getuid() != entry->pw_uid) {
            fprintf(stderr, "%s must be called with uid praktomat\n", argv[0]);
            return 1;
        }
    }

    // Check for root
    if (geteuid() != 0) {
        fprintf(stderr, "%s must be suid root\n", argv[0]);
        return 1;
    }

    // create new sesion (because limits are set per session)
    pid_t sid = getsid(0);
    pid_t pid = getpid();
    if (sid != pid) {
        if (setsid() < 0 && errno != EPERM) {
            perror("setsid");
            return 1;
        }
    }

    // create new process group
    pid_t pgid = getpgid(0);
    // fprintf(stderr, "pgid=%ld, pid=%ld\n", (long)pgid, (long)pid);
    if (pgid != pid) {
        if (setpgid(0, 0) < 0) {
            perror("setpgid)");
            return 1;
        }
    }

    // remove network
    if (unshare(CLONE_NEWNET) < 0) {
        perror("unshare(CLONE_NEWNET)");
        return 1;
    }

    // rlimit CPU
    struct rlimit limit;
    limit.rlim_cur = 25; // sec soft
    limit.rlim_max = 30; // sec hard
    if (setrlimit(RLIMIT_CPU, &limit) < 0) {
        perror("setrlimit CPU");
        return 1;
    }     

    // rlimit NPROC (fork)
    limit.rlim_cur = 250; // number of threads soft
    limit.rlim_max = 250; // number of threads hard
    if (setrlimit(RLIMIT_NPROC, &limit) < 0) {
        perror("setrlimit NPROC");
        return 1;
    }    

    // rlimit AS (address space)
    // struct rlimit limit;
    limit.rlim_cur = 1024 * 1024 * 500; // bytes soft (500MB)
    limit.rlim_max = 1024 * 1024 * 600; // bytes hard (600MB)
    if (setrlimit(RLIMIT_AS, &limit) < 0) {
        perror("setrlimit AS");
        return 1;
    }

    // rlimit RLIMIT_NOFILE
    limit.rlim_cur = 64; // number of open file handles soft
    limit.rlim_max = 64; // number of open file handles hard
    if (setrlimit(RLIMIT_NOFILE, &limit) < 0) {
        perror("setrlimit RLIMIT_NOFILE");
        return 1;
    }     

    // search for tester
    struct passwd *entry = getpwnam("tester");
    if (!entry) {
        perror("getpwnam(tester)");
        return 1;
    }


	// change root directory
    if (chroot(".") < 0) {
        perror("chroot");
        return 1;
    }  	
	
    // become tester
    if (setgid(entry->pw_gid) < 0) {
        perror("setgid");
        return 1;
    }
    if (setuid(entry->pw_uid) < 0) {
        perror("setuid");
        return 1;
    }

    // execute command
    execvp(argv[1], argv+1);
    perror(argv[1]);
    return 1;
}
