import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Copyright from '../internals/components/Copyright';
import SessionsChart from './SessionsChart';
import {useEffect, useState} from "react";
import useMqtt  from '../../assets/usemqtt';
import type { DataPoint } from '../../assets/helpers';

export default function MainGrid() {

  const [sent, setSent] = useState<DataPoint[]>([]);
  const [received, setReceived] = useState<DataPoint[]>([]);
  const [bytesIn, setBytesIn] = useState<DataPoint[]>([]);
  const [bytesOut, setBytesOut] = useState<DataPoint[]>([]);

  function getRandomInt(min:number, max:number) {
  min = Math.ceil(min);
  max = Math.floor(max);
  return Math.floor(Math.random() * (max - min + 1)) + min;
}


  const mqtt_settings = {
    url: 'ws://' + import.meta.env.VITE_MQTT_HOST,
    client_id: `web-client-${getRandomInt(1, 100)}`,
    config: {
      port: import.meta.env.VITE_MQTT_PORT
    }
  };

  const {mqttSubscribe, isConnected, messageQueue, messageTick} = useMqtt(mqtt_settings);

  useEffect(() => {
    if (isConnected) {
      mqttSubscribe('$SYS/broker/messages/publish/#');
      mqttSubscribe('$SYS/broker/load/bytes/#');
    }
  }, [isConnected, mqttSubscribe]);

  useEffect(() => {

    while (messageQueue.current.length > 0) {
      const payload = messageQueue.current.shift()!;
            try {

        const d = JSON.parse(payload.message);
        if (payload.topic === '$SYS/broker/messages/publish/sent') {
          const newPoint: DataPoint = {
            timestamp: new Date().toISOString(),
            value: d
          };
          setSent(sent => [...sent, newPoint]);
        } else if (payload.topic === '$SYS/broker/messages/publish/received') {
          const newPoint: DataPoint = {
            timestamp: new Date().toISOString(),
            value: d
          }
          setReceived(received => [...received, newPoint]);
        } else if (payload.topic === '$SYS/broker/load/bytes/received') {
          const newPoint: DataPoint = {
            timestamp: new Date().toISOString(),
            value: d
          }
          setBytesIn(bytesIn => [...bytesIn, newPoint]);
        } else if (payload.topic === '$SYS/broker/load/bytes/sent') {
          const newPoint: DataPoint = {
            timestamp: new Date().toISOString(),
            value: d
          }
          setBytesOut(bytesOut => [...bytesOut, newPoint]);
        }
      }
      catch (e) {
        console.log(e);
      }
    }
  }, [messageTick]);





  return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      {/* cards */}
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Overview
      </Typography>
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        <Grid size={{ xs: 12, md: 6 }}>
          <SessionsChart title={'Sent Messages'} label={'Messages'} data={sent} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <SessionsChart title={'Received Messages'} label={'Messages'} data={received} />
        </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
          <SessionsChart title={'Bytes Out'} label={'Bytes'} data={bytesOut} />
        </Grid>
        <Grid size={{ xs: 12, md: 6 }}>
          <SessionsChart title={'Bytes In'} label={'Bytes'} data={bytesIn} />
        </Grid>
      </Grid>

      <Grid container spacing={2} columns={12}>
        <Grid size={{ xs: 12, lg: 9 }}></Grid>
        <Grid size={{ xs: 12, lg: 3 }}>
          <Stack gap={2} direction={{ xs: 'column', sm: 'row', lg: 'column' }}></Stack>
        </Grid>
      </Grid>
      <Copyright sx={{ my: 4 }} />
    </Box>
  );
}
