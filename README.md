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

How to install and run the processor as SNAP plugin 
---------------------------------------------------

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
> **Optical / Preprocessing / Sentinel-2 Radiometric Uncertainty Tool
  
Or in batch mode using SNAP's `gpt` command-line tool found in `${SNAP_HOME}/bin`:
```
> gpt S2RutOp -h
```  
For general help on using gpt call:
```
> gpt -h
```  

# THIS following needs review

## Modifying, running and debugging the processor code
This section explains how to run and debug the S2-RUT processor code from a Java IDE without having to install the plugin into SNAP.

You will need to install
* SNAP with the Sentinel-2 Toolbox (S3TBX) from http://step.esa.int/main/download/
* PyCharm (Community Edition) IDE from https://www.jetbrains.com/pycharm/download/

Start PyCharm and select **File / New / Project from Existing Sources**. Select the `pom.xml` (Maven project file) in the source directory. Leve all default settings as they are and click **Next** until PyCharm asks for the JDK. Select the installed JDK from above and finish the dialog.

From the main menu select **Run / Edit Configurations**. In the dialog click the **+** (add) button and select **JAR Application**. Then the settings are as follows:

* **Name**: SNAP Desktop
* **Path to JAR:** `${SNAP_HOME}/snap/snap/core/snap-main.jar`
* **VM options:** `-Xmx4G -Dorg.netbeans.level=INFO -Dsun.java2d.noddraw=true -Dsun.awt.nopixfmt=true -Dsun.java2d.dpiaware=false` 
* **Program arguments:** `--userdir ${S2RUT_HOME}/target/testdir --clusters ${S2RUT_HOME}/target/nbm/netbeans/extra --patches ${S2RUT_HOME}/$/target/classes`
* **Working directory:** `${SNAP_HOME}`

where 

* `${SNAP_HOME}` must be replaced by your SNAP installation directory
* `${S2RUT_HOME}` must be replaced by your S2RUT project directory (where the `pom.xml` is located in)

