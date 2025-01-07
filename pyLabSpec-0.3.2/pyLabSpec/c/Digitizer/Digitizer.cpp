///
/// Keysight IVI-C Driver Example Program
///
/// Initializes the driver, reads a few Identity interface properties, and performs a
/// simple record acquisition.
///
/// See driver help topic "Programming with the IVI-C Driver in Various ADEs"
/// for additional programming information.
///
/// Runs in simulation mode without an instrument.
///

#include "AgMD2.h"

#include <iostream>
using std::cout;
using std::cerr;
using std::hex;
#include <vector>
using std::vector;
#include <stdexcept>
using std::runtime_error;

#define checkApiCall( f ) do { ViStatus s = f; testApiCall( s, #f ); } while( false )
#define checkApiCallNoEx( f ) do { ViStatus s = f; testApiCallNoEx( s, #f ); } while( false )


// Edit resource and options as needed. Resource is ignored if option has Simulate=true.
// An input signal is necessary if the example is run in non simulated mode, otherwise
// the acquisition will time out.
ViChar resource[] = "PXI1::0::0::INSTR";
ViChar options[]  = "Simulate=false, DriverSetup= Model=U5310A";


ViInt64 const recordSize = 1000000;
ViInt64 const numRecords = 1;

// Utility function to check status error during driver API call.
void testApiCall( ViStatus status, char const * functionName )
{
    ViInt32 ErrorCode;
    ViChar ErrorMessage[512];

    if( status>0 ) // Warning occurred.
    {
        AgMD2_GetError( VI_NULL, &ErrorCode, sizeof( ErrorMessage ), ErrorMessage );
        cerr << "** Warning during " << functionName << ": 0x" << hex << ErrorCode << ", " << ErrorMessage << '\n';

    }
    else if( status<0 ) // Error occurred.
    {
        AgMD2_GetError( VI_NULL, &ErrorCode, sizeof( ErrorMessage ), ErrorMessage );
        cerr << "** ERROR during " << functionName << ": 0x" << hex << ErrorCode << ", " << ErrorMessage << '\n';
        throw runtime_error( ErrorMessage );
    }
}

void testApiCallNoEx( ViStatus status, char const * functionName )
{
    ViInt32 ErrorCode;
    ViChar ErrorMessage[512];

    if( status>0 ) // Warning occurred.
    {
        AgMD2_GetError( VI_NULL, &ErrorCode, sizeof( ErrorMessage ), ErrorMessage );
        cerr << "** Warning during " << functionName << ": 0x" << hex << ErrorCode << ", " << ErrorMessage << '\n';

    }
    else if( status<0 ) // Error occurred.
    {
        AgMD2_GetError( VI_NULL, &ErrorCode, sizeof( ErrorMessage ), ErrorMessage );
        cerr << "** ERROR during " << functionName << ": 0x" << hex << ErrorCode << ", " << ErrorMessage << '\n';
    }
}


// -------------------------------------------------
// Session
// -------------------------------------------------

extern "C" int open_session()
{
    cout << "SimpleAcquisition\n\n";

    // Initialize the driver. See driver help topic "Initializing the IVI-C Driver" for additional information.
    ViSession session;
    ViBoolean const idQuery = VI_FALSE;
    ViBoolean const reset   = VI_FALSE;
    checkApiCall( AgMD2_InitWithOptions( resource, idQuery, reset, options, &session ) );

    cout << session;
    cout << "Driver initialized \n";

    return session;
}	

extern "C" int close_session(ViSession session)
{
    // Close the driver.
    checkApiCall( AgMD2_close( session ) );
    cout << "\nDriver closed\n";

    return 0;
}

extern "C" int info(ViSession session)
{

    // Read and output a few attributes.
    ViChar str[128];
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_PREFIX,               sizeof( str ), str ) );
    cout << "Driver prefix:      " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_REVISION,             sizeof( str ), str ) );
    cout << "Driver revision:    " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_VENDOR,               sizeof( str ), str ) );
    cout << "Driver vendor:      " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_DESCRIPTION,          sizeof( str ), str ) );
    cout << "Driver description: " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_MODEL,                     sizeof( str ), str ) );
    cout << "Instrument model:   " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_INFO_OPTIONS,              sizeof( str ), str ) );
    cerr << "Instrument options: " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_FIRMWARE_REVISION,         sizeof( str ), str ) );
    cout << "Firmware revision:  " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_INFO_SERIAL_NUMBER_STRING, sizeof( str ), str ) );
    cout << "Serial number:      " << str << '\n';

    return 0;
}

// -------------------------------------------------
// Get and Set Settings
// -------------------------------------------------
extern "C" ViReal64 getTriggerDelay(ViSession session)
{   
    ViReal64 val;
    checkApiCallNoEx( AgMD2_GetAttributeViReal64( session, "", AGMD2_ATTR_TRIGGER_DELAY, &val) );
    return val;
}

extern "C" ViReal64 getAttributeViReal64(ViSession session, ViAttr attr )
{   
    ViReal64 val;
    checkApiCallNoEx( AgMD2_GetAttributeViReal64( session, "", attr, &val) );
    return val;
}

extern "C" ViInt64 getAttributeViInt64(ViSession session, ViAttr attr )
{   
    ViInt64 val;
    checkApiCallNoEx( AgMD2_GetAttributeViInt64( session, "", attr, &val) );
    return val;
}

extern "C" ViInt32 getAttributeViInt32(ViSession session, ViAttr attr )
{   
    ViInt32 val;
    checkApiCallNoEx( AgMD2_GetAttributeViInt32( session, "", attr, &val) );
    return val;
}

extern "C" ViChar * getAttributeViString(ViSession session, ViAttr attr )
{   
    ViChar* str = new ViChar[128];
    checkApiCallNoEx( AgMD2_GetAttributeViString( session, "", attr, sizeof(str), str) );
    return str;
}

extern "C" ViBoolean getAttributeViBoolean(ViSession session, ViAttr attr )
{   
    ViBoolean val;
    checkApiCallNoEx( AgMD2_GetAttributeViBoolean( session, "", attr, &val) );
    return val;
}

extern "C" int setAttributeViReal64(ViSession session, ViAttr attr, ViReal64 val )
{   
    checkApiCallNoEx( AgMD2_SetAttributeViReal64( session, "", attr, val) );
    return 0;
}

extern "C" int setAttributeViInt64(ViSession session, ViAttr attr, ViInt64 val )
{   
    checkApiCallNoEx( AgMD2_SetAttributeViInt64( session, "", attr, val) );
    return 0;
}

extern "C" int setAttributeViInt32(ViSession session, ViAttr attr, ViInt32 val )
{   
    checkApiCallNoEx( AgMD2_SetAttributeViInt32( session, "", attr, val) );
    return 0;
}

extern "C" int setAttributeViString(ViSession session, ViAttr attr, ViConstString val )
{   
    checkApiCallNoEx( AgMD2_SetAttributeViString( session, "", attr, val) );
    return 0;
}

extern "C" int setAttributeViBoolean(ViSession session, ViAttr attr, ViBoolean val )
{   
    checkApiCallNoEx( AgMD2_SetAttributeViBoolean( session, "", attr, val) );
    return 0;
}



// -------------------------------------------------
// Acquisition
// -------------------------------------------------

extern "C" int configureAcquisition(ViSession session, ViConstString channel, ViInt32 numRecords, ViInt32 recordSize, ViReal64 range, ViReal64 offset) 
{

    // Configure the acquisition.
    // ViReal64 const range = 1.0;
    // ViReal64 const offset = 0.0;
    ViInt32 const coupling = AGMD2_VAL_VERTICAL_COUPLING_DC;
    cout << "\nConfiguring acquisition\n";
    cout << "Range:              " << range << '\n';
    cout << "Offset:             " << offset << '\n';
    cout << "Coupling:           " << ( coupling?"DC":"AC" ) << '\n';
    // checkApiCall( AgMD2_ConfigureChannel( session, "Channel1", range, offset, coupling, VI_TRUE ) );
    checkApiCallNoEx( AgMD2_ConfigureChannel( session, channel, range, offset, coupling, VI_TRUE ) );
    cout << "Number of records:  " << numRecords << '\n';
    cout << "Record size:        " << recordSize << '\n';
    checkApiCallNoEx( AgMD2_SetAttributeViInt64( session, "", AGMD2_ATTR_NUM_RECORDS_TO_ACQUIRE, numRecords ) );
    checkApiCallNoEx( AgMD2_SetAttributeViInt64( session, "", AGMD2_ATTR_RECORD_SIZE,            recordSize ) );

    checkApiCallNoEx( AgMD2_SetAttributeViInt32( session, "", AGMD2_ATTR_ACQUISITION_MODE, AGMD2_VAL_ACQUISITION_MODE_NORMAL ) );
    checkApiCallNoEx( AgMD2_ApplySetup( session ) );

   
    return 0;
}

extern "C" int configureAvgAcquisition(ViSession session, ViConstString channel, ViInt32 numAverages, ViInt32 recordSize, ViReal64 range, ViReal64 offset)
{
    // Configure the acquisition.
    // cout << "\nConfiguring acquisition\n";
    // ViInt64 const recordSize = 1600;
    ViInt64 const numRecords = 1;
    // ViReal64 const range = 1.0;
    // ViReal64 const offset = 0.0;
    ViInt32 const coupling = AGMD2_VAL_VERTICAL_COUPLING_DC;
    cout << "Range:              " << range << "\n";
    cout << "Offset:             " << offset << "\n";
    cout << "Coupling:           " << ( coupling ? "DC" : "AC" ) << "\n";
    checkApiCallNoEx( AgMD2_ConfigureChannel( session, channel, range, offset, coupling, VI_TRUE ) );
    cout << "Record size:        " << recordSize << "\n";
    checkApiCallNoEx( AgMD2_SetAttributeViInt64( session, "", AGMD2_ATTR_NUM_RECORDS_TO_ACQUIRE, numRecords ) );
    checkApiCallNoEx( AgMD2_SetAttributeViInt64( session, "", AGMD2_ATTR_RECORD_SIZE, recordSize ) );
    cout << "Number of averages: " << numAverages << "\n";
    checkApiCallNoEx( AgMD2_SetAttributeViInt32( session, "", AGMD2_ATTR_ACQUISITION_NUMBER_OF_AVERAGES, numAverages ) );
    // Have to disable "Channel2" in order to set Averager mode for U5309A
    //if( instrModel=="U5309A" )
    //    checkApiCall( AgMD2_SetAttributeViBoolean( session, "Channel2", AGMD2_ATTR_CHANNEL_ENABLED, VI_FALSE ) );
    checkApiCallNoEx( AgMD2_SetAttributeViInt32( session, "", AGMD2_ATTR_ACQUISITION_MODE, AGMD2_VAL_ACQUISITION_MODE_AVERAGER ) );
    checkApiCallNoEx( AgMD2_ApplySetup( session ) );

    return 0;
}

extern "C" int acquireData(ViSession session, ViInt32 timeoutInMs) 
{
    // Perform the acquisition.
    //ViInt32 const timeoutInMs = 1000;
    // cout << "\nPerforming acquisition\n";
    checkApiCallNoEx( AgMD2_InitiateAcquisition( session ) );
    return AgMD2_WaitForAcquisitionComplete( session, timeoutInMs );
    // cout << "Acquisition completed\n";

    //return 0;
}

extern "C" int initiateAcquisition(ViSession session) 
{
    // Perform the acquisition.
    //ViInt32 const timeoutInMs = 1000;
    // cout << "\nPerforming acquisition\n";
    checkApiCallNoEx( AgMD2_InitiateAcquisition( session ) );

    //return 0;
}

extern "C" int abortAcquisition(ViSession session)
{
	checkApiCallNoEx( AgMD2_Abort( session ) );
	return 0;
}

extern "C" int waitForAcquisitionComplete(ViSession session, ViInt32 timeoutInMs)
{
	checkApiCallNoEx( AgMD2_WaitForAcquisitionComplete( session, timeoutInMs ) );
}

// -------------------------------------------------
// Trigger
// -------------------------------------------------


extern "C" int configureTrigger(ViSession session)
{
    // Configure the trigger.
    cout << "\nConfiguring trigger\n";
    checkApiCallNoEx( AgMD2_SetAttributeViString( session, "", AGMD2_ATTR_ACTIVE_TRIGGER_SOURCE, "Internal1" ) );

    return 0;
}

extern "C" int configureExternalTrigger(ViSession session, ViReal64 level, ViConstString slope)
{
    // Configure the trigger.
    cout << "\nConfiguring trigger\n";
    cout << "Trigger Level:             " << level << "\n";
    checkApiCallNoEx( AgMD2_SetAttributeViString( session, "", AGMD2_ATTR_ACTIVE_TRIGGER_SOURCE, "External1" ) );
    if( slope=="negative" ) {
       checkApiCallNoEx( AgMD2_ConfigureEdgeTriggerSource( session, "External1", level, AGMD2_VAL_NEGATIVE) );
    } else {
       checkApiCallNoEx( AgMD2_ConfigureEdgeTriggerSource( session, "External1", level, AGMD2_VAL_POSITIVE) );
    }
    return 0;
}

// -------------------------------------------------
// Calibration
// -------------------------------------------------

extern "C" int calibrate(ViSession session)
{
    // Calibrate the instrument.
    cout << "\nPerforming self-calibration\n";
    checkApiCallNoEx( AgMD2_SelfCalibrate( session ) );
}

// -------------------------------------------------
// Data Transfer
// -------------------------------------------------

extern "C" int getData(ViSession session, ViConstString channel, ViInt64 recordSize, size_t size, double *outdata)
{
    // Fetch the acquired data in array.
    ViInt64 arraySize = 0;
    ViInt64 numRecords = 1;
    checkApiCallNoEx( AgMD2_QueryMinWaveformMemory( session, 16, numRecords, 0, recordSize, &arraySize ) );

    vector<ViInt16> dataArray( arraySize );
    ViInt64 actualPoints, firstValidPoint;
    ViReal64 initialXOffset[numRecords], initialXTimeSeconds[numRecords], initialXTimeFraction[numRecords];
    ViReal64 xIncrement = 0.0, scaleFactor = 0.0, scaleOffset = 0.0;
    try
    {
//       checkApiCall( AgMD2_FetchWaveformInt16( session, "Channel1", arraySize, &dataArray[0],
       checkApiCallNoEx( AgMD2_FetchWaveformInt16( session, channel, arraySize, &dataArray[0],
           &actualPoints, &firstValidPoint, initialXOffset, initialXTimeSeconds, initialXTimeFraction,
           &xIncrement, &scaleFactor, &scaleOffset ) );
    }
    catch (const runtime_error& error)
    {
      return 1;	    
    }

    // Convert data to Volts.
    // cout << "\nProcessing data\n";
    for( ViInt64 currentPoint = 0; currentPoint< actualPoints; ++currentPoint )
    {
        ViReal64 valueInVolts = dataArray[firstValidPoint + currentPoint]*scaleFactor + scaleOffset;
	outdata[currentPoint] = valueInVolts;
    }
    
    // cout << "Processing completed\n";

    return 0;

}

extern "C" int getDataMultiRecord(ViSession session, ViConstString channel, ViInt64 numRecords, ViInt64 recordSize, size_t size, double *outdata)
{
    // Fetch the acquired data in array.
    ViInt64 arraySize = 0;
    checkApiCall( AgMD2_QueryMinWaveformMemory( session, 16, numRecords, 0, recordSize, &arraySize ) );

    vector<ViInt16> dataArray( arraySize );
    ViInt64 actualRecords = 0, waveformArrayActualSize = 0;
    ViInt64 actualPoints[numRecords], firstValidPoint[numRecords];
    ViReal64 initialXOffset[numRecords], initialXTimeSeconds[numRecords], initialXTimeFraction[numRecords];
    ViReal64 xIncrement = 0.0, scaleFactor = 0.0, scaleOffset = 0.0;
    // checkApiCall( AgMD2_FetchMultiRecordWaveformInt16( session, "Channel1", 0, numRecords, 0, recordSize, arraySize,
    checkApiCallNoEx( AgMD2_FetchMultiRecordWaveformInt16( session, channel, 0, numRecords, 0, recordSize, arraySize,
                  &dataArray[0], &waveformArrayActualSize, &actualRecords, actualPoints, firstValidPoint, initialXOffset,
                  initialXTimeSeconds, initialXTimeFraction, &xIncrement, &scaleFactor, &scaleOffset ) );

    // Convert data to Volts.
    // cout << "\nProcessing data\n";
    for( ViInt64 currentRecord = 0; currentRecord<numRecords; ++currentRecord )
    {
        for( ViInt64 currentPoint = 0; currentPoint<actualPoints[currentRecord]; ++currentPoint )
        {
            ViReal64 valueInVolts = dataArray[firstValidPoint[currentRecord]+currentPoint]*scaleFactor + scaleOffset;
	    outdata[currentRecord * recordSize + currentPoint] = valueInVolts;
        }
    }

    return 0;
 
}

extern "C" int getDataAvg(ViSession session, ViConstString channel, ViInt64 recordSize, size_t size, double *outdata)
{
    // Fetch the acquired data in array.
    ViInt64 arraySize = 0;
    ViInt64 numRecords = 1;
    checkApiCallNoEx( AgMD2_QueryMinWaveformMemory( session, 32, 1, 0, recordSize, &arraySize ) );

    vector<ViInt32> dataArray( arraySize );
    ViInt32 actualAverages = 0;
    ViInt64 actualRecords = 0;
    ViInt64 actualPoints[numRecords], firstValidPoint[numRecords];
    ViReal64 initialXTimeSeconds[numRecords], initialXTimeFraction[numRecords];
    ViReal64 initialXOffset = 0.0, XIncrement = 0.0, scaleFactor = 0.0, scaleOffset = 0.0;
    ViInt32 flags[numRecords];
    // checkApiCall( AgMD2_FetchAccumulatedWaveformInt32( session, "Channel1", 0, 1, 0, recordSize, arraySize, &dataArray[0],
    checkApiCallNoEx( AgMD2_FetchAccumulatedWaveformInt32( session, channel, 0, 1, 0, recordSize, arraySize, &dataArray[0],
        &actualAverages, &actualRecords, actualPoints, firstValidPoint,
        &initialXOffset, initialXTimeSeconds, initialXTimeFraction,
        &XIncrement, &scaleFactor, &scaleOffset, flags ) );

    // Convert data to Volts.
    // cout << "\nProcessing data\n";
    for( ViInt64 currentRecord=0 ; currentRecord<actualRecords ; ++currentRecord )
    {
        for( ViInt64 currentPoint=0 ; currentPoint<actualPoints[currentRecord] ; ++currentPoint )
        {
            ViInt32 const valueRaw = dataArray[firstValidPoint[currentRecord]+currentPoint];
            ViReal64 const valueInVolts = ViReal64( valueRaw )*scaleFactor + scaleOffset;
            //(void)valueInVolts; // Use it!
	    outdata[currentPoint] = valueInVolts;
        }
    }
    return 0; 
}

int main()
{
    cout << "SimpleAcquisition\n\n";

    // Initialize the driver. See driver help topic "Initializing the IVI-C Driver" for additional information.
    ViSession session;
    ViBoolean const idQuery = VI_FALSE;
    ViBoolean const reset   = VI_FALSE;
    checkApiCall( AgMD2_InitWithOptions( resource, idQuery, reset, options, &session ) );

    cout << "Driver initialized \n";

    // Read and output a few attributes.
    ViChar str[128];
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_PREFIX,               sizeof( str ), str ) );
    cout << "Driver prefix:      " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_REVISION,             sizeof( str ), str ) );
    cout << "Driver revision:    " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_VENDOR,               sizeof( str ), str ) );
    cout << "Driver vendor:      " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_SPECIFIC_DRIVER_DESCRIPTION,          sizeof( str ), str ) );
    cout << "Driver description: " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_MODEL,                     sizeof( str ), str ) );
    cout << "Instrument model:   " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_INFO_OPTIONS,              sizeof( str ), str ) );
    cerr << "Instrument options: " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_FIRMWARE_REVISION,         sizeof( str ), str ) );
    cout << "Firmware revision:  " << str << '\n';
    checkApiCall( AgMD2_GetAttributeViString( session, "", AGMD2_ATTR_INSTRUMENT_INFO_SERIAL_NUMBER_STRING, sizeof( str ), str ) );
    cout << "Serial number:      " << str << '\n';

    ViBoolean simulate;
    checkApiCall( AgMD2_GetAttributeViBoolean( session, "", AGMD2_ATTR_SIMULATE, &simulate ) );
    cout << "\nSimulate:           " << ( simulate?"True":"False" ) << '\n';
    cout << "Processing completed\n";

    // Close the driver.
    checkApiCall( AgMD2_close( session ) );
    cout << "\nDriver closed\n";

    return 0;
}

