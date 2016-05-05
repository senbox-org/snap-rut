# S2-RUT
S2 RUT: Radiometric Uncertainty Tool for Sentinel-2 MSI L1C products (ESA IDEAS+ Programme)

##How to build?
First the following tools are needed at least:
- [Oracle JDK](http://www.oracle.com/technetwork/java/javase/downloads/index.html) version 8 or later
- [Git client](https://git-scm.com) for fetching the source code
- Build tool [Maven](http://maven.apache.org/) must be installed (version 3 or later)


Clone or fork the repository at [GitHub](https://github.com/senbox-org/snap-rut)
```
> git clone https://github.com/senbox-org/snap-rut.git
> cd snap-rut
```

You can update your checked-out sources from the remote repository by running 
```
> git pull --rebase
```

Incremental build with Maven:
```
> mvn package
```

Clean build:
```
> mvn clean package
```  

If you encounter test failures:
```
> mvn clean package -DskipTests=true
```

The build creates a SNAP plugin module file `<project_dir>/target/nbm/snap-rut-<version>.nbm`

## How to install and run the processor as SNAP plugin

Start SNAP (Desktop UI) and find the plugin manager in the main menu at 
> **Tools / Plugins**

Then 
* select tab **Downloaded**, 
* click button **Add Files** and 
* select the plugin module file `<project_dir>/target/nbm/s3tbx-c2rcc-<version>.nbm`. 
* Click **Install**, 
* then **Close** and 
* restart SNAP.
* 
Once the S2-RUT processor is installed into SNAP it can be run from the SNAP Desktop UI's main menu at
**Optical / Preprocessing / Sentinel-2 Radiometric Uncertainty Tool**
  
Or in batch mode using SNAP's `gpt` command-line tool found in `${SNAP_HOME}/bin`:
```
> gpt S2RutOp -h
```  
For general help on using gpt call:
```
> gpt -h
```  

## How to Configure SNAP to pick up the build output automatically

Find the `etc` folder in the SNAP installation directory. Inside this directory you will find the `snap.conf` file.
Change the access right of it so that you are allowed to make changes to it.
There you will find the `extra_clusters` property.
Specify the path, to the cluster folder of the build output directory.
```
extra_clusters="<project_dir>/target/nbm/netbeans/snap"
```
Ensure to remove the '**#**' character at the beginning of the line.

Now when you start SNAP the build output is automatically used by SNAP and you can test the latest builds.