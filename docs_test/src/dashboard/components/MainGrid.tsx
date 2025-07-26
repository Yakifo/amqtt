import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Copyright from '../Copyright';
import DashboardChart from './DashboardChart.tsx';
import {useEffect, useState} from "react";
// @ts-ignore
import useMqtt from '../../assets/usemqtt';
import {type DataPoint, getMQTTSettings, secondsToDhms, type TopicMap} from '../../assets/helpers';
import DescriptionPanel from "./DescriptionPanel";

export default function MainGrid() {

  const [sent, setSent] = useState<DataPoint[]>([]);
  const [received, setReceived] = useState<DataPoint[]>([]);
  const [bytesIn, setBytesIn] = useState<DataPoint[]>([]);
  const [bytesOut, setBytesOut] = useState<DataPoint[]>([]);
  const [clientsConnected, setClientsConnected] = useState<DataPoint[]>([]);
  const [serverStart, setServerStart] = useState<string>('');
  const [serverUptime, setServerUptime] = useState<string>('');
  const [cpuPercent, setCpuPercent] = useState<DataPoint[]>([]);
  const [memSize, setMemSize] = useState<DataPoint[]>([]);
  const [version, setVersion] = useState<string>('');

  const {mqttSubscribe, isConnected, messageQueue, messageTick} = useMqtt(getMQTTSettings());

  const topicMap: TopicMap = {
    '$SYS/broker/messages/publish/sent': {current: sent, update: setSent},
    '$SYS/broker/messages/publish/received': {current: received, update: setReceived},
    '$SYS/broker/load/bytes/received': {current: bytesIn, update: setBytesIn},
    '$SYS/broker/load/bytes/sent': {current: bytesOut, update: setBytesOut},
    '$SYS/broker/clients/connected': {current: clientsConnected, update: setClientsConnected},
    '$SYS/broker/cpu/percent': {current: cpuPercent, update: setCpuPercent},
    '$SYS/broker/heap/size': {current: memSize, update: setMemSize},
  };

  useEffect(() => {
    if (isConnected) {
      for(const topic in topicMap) {
        mqttSubscribe(topic);
      }
      mqttSubscribe('$SYS/broker/version');
      mqttSubscribe('$SYS/broker/uptime/formatted');
      mqttSubscribe('$SYS/broker/uptime');
    }
  }, [isConnected, mqttSubscribe]);

  useEffect(() => {

    while (messageQueue.current.length > 0) {
      const payload = messageQueue.current.shift()!;
      try {

        const d = payload.message;

        if(payload.topic in topicMap) {
          const { update } = topicMap[payload.topic];
          const newPoint: DataPoint = {
            time: new Date().toISOString(),
            timestamp: Date.now(),
            value: d
          };
          update(current => [...current, newPoint])
        } else if (payload.topic === '$SYS/broker/uptime/formatted') {
          const dt = new Date(d + "Z");
          setServerStart(dt.toLocaleString());
        } else if (payload.topic === '$SYS/broker/uptime') {
          const {days, hours, minutes, seconds} = secondsToDhms(d);
          setServerUptime(`${days} days, ${hours} hours, ${minutes} minutes, ${seconds} seconds`);
        } else if(payload.topic === '$SYS/broker/version') {
          setVersion(d);
        }
      } catch (e) {
        console.log(e);
      }
    }
  }, [messageTick, messageQueue]);

  const upTime = () => {
    return isConnected && serverUptime ? <>
      <strong>aMQTT broker</strong> {version.replace('aMQTT version ', 'v')} <strong>started at </strong> {serverStart} &nbsp;
      <strong>up for</strong> {serverUptime}
    </> : <></>;
  }

  return (
    <Box sx={{width: '100%', maxWidth: {sm: '100%', md: '1700px'}}}>
      {/* cards */}

      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <DescriptionPanel/>
      </Grid>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{mb: (theme) => theme.spacing(2)}}
      >
        <Grid size={{xs: 12, md: 12}}>
          {upTime()}
      </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <DashboardChart title={'Sent Messages'} label={''} data={sent} isConnected={isConnected} isPerSecond/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <DashboardChart title={'Received Messages'} label={''} data={received} isConnected={isConnected} isPerSecond/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <DashboardChart title={'Bytes Out'} label={''} data={bytesOut} isConnected={isConnected} isBytes/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <DashboardChart title={'Bytes In'} label={''} data={bytesIn} isConnected={isConnected} isBytes/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <DashboardChart title={'Clients Connected'} label={''} data={clientsConnected} isConnected={isConnected}/>
        </Grid>
        <Grid size={{xs: 12, md: 6}}>
          <Grid container spacing={2} columns={2}>
            <Grid size={{lg:1}}>
              <DashboardChart title={'CPU'} label={'%'} data={cpuPercent} decimals={2} isConnected={isConnected}/>
            </Grid>
            <Grid size={{lg:1}}>
              <DashboardChart title={'Memory'} label={'MB'} data={memSize} decimals={1} isConnected={isConnected}/>
            </Grid>
          </Grid>
        </Grid>
      </Grid>

      <Grid container spacing={2} columns={12}>
        <Grid size={{xs: 12, lg: 9}}></Grid>
        <Grid size={{xs: 12, lg: 3}}>
          <Stack gap={2} direction={{xs: 'column', sm: 'row', lg: 'column'}}></Stack>
        </Grid>
      </Grid>
      <Copyright sx={{my: 4}}/>
    </Box>
  );
}
