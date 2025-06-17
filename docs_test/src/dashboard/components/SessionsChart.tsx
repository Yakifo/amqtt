import { useTheme } from '@mui/material/styles';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import { LineChart } from '@mui/x-charts/LineChart';
import CountUp from 'react-countup';
import type { DataPoint } from '../../assets/helpers.jsx';
import {CircularProgress} from "@mui/material";

const currentTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

function formatDate(date: Date) {

  return date.toLocaleTimeString('en-US', {
    timeZone: currentTimeZone,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

}


function AreaGradient({ color, id }: { color: string; id: string }) {
  return (
    <defs>
      <linearGradient id={id} x1="50%" y1="0%" x2="50%" y2="100%">
        <stop offset="0%" stopColor={color} stopOpacity={0.5} />
        <stop offset="100%" stopColor={color} stopOpacity={0} />
      </linearGradient>
    </defs>
  );
}

function NoDataDisplay(props: any) {
  return <>
    {!props.isConnected ? <div style={{height: 250, width: 600, paddingTop: 50}}>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          Connecting...
        </Typography>
      <CircularProgress size={60}/>
      </div> :
      <div style={{height: 250, width: 600, paddingTop: 50}}>
        <Typography component="h2" variant="subtitle2" gutterBottom>
          Connected, waiting for data...
        </Typography>
        <CircularProgress size={60}/>
      </div>}
  </>

}

function LinearChart(props: any) {

  const theme = useTheme();

    const colorPalette = [
    theme.palette.primary.light,
    theme.palette.primary.main,
    theme.palette.primary.dark,
  ];

  const label: string = props.label || '--';

  return <LineChart
          colors={colorPalette}
          xAxis={[
            {
              scaleType: 'point',
              data: props.data.map( (dp:DataPoint) =>
                formatDate(new Date(dp.timestamp))
              ),
              tickInterval: (_index, i) => (i + 1) % (Math.floor(props.data.length/10) + 1) === 0,
            },
          ]}
          series={[
            {
              id: 'direct',
              label: label,
              showMark: false,
              curve: 'linear',
              stack: 'total',
              area: true,
              stackOrder: 'ascending',
              data: props.data.map( (dp:DataPoint) => dp.value),
            }
          ]}
          height={175}
          margin={{ left: 50, right: 20, top: 20, bottom: 20 }}
          grid={{ horizontal: true }}
          sx={{
            '& .MuiAreaElement-series-organic': {
              fill: "url('#organic')",
            },
            '& .MuiAreaElement-series-referral': {
              fill: "url('#referral')",
            },
            '& .MuiAreaElement-series-direct': {
              fill: "url('#direct')",
            },
          }}
          hideLegend
          slotProps={{
            legend: {
            },
          }}
        >

          <AreaGradient color={theme.palette.primary.main} id="direct" />
        </LineChart>
}

export default function SessionsChart(props: any) {

  return (
    <Card variant="outlined" sx={{ width: '100%' }}>
      <CardContent>
        <Typography component="h1" variant="subtitle1" gutterBottom>
          {props.title}
        </Typography>
        <Stack sx={{ justifyContent: 'space-between' }}>
          <Stack
            direction="row"
            sx={{
              alignContent: { xs: 'center', sm: 'flex-start' },
              alignItems: 'center',
              gap: 1,
            }}
          >
            <Typography variant="h4" component="p">

              { props.data.length < 2 ? "" :
              <CountUp
                start={props.data[props.data.length - 2].value}
                end={props.data[props.data.length - 1].value}
                duration={5}/>}
            </Typography>
          </Stack>
        </Stack>
        { props.data.length < 2 ? <NoDataDisplay isConnected={props.isConnected}/> :
          <LinearChart {...props} /> }

      </CardContent>
    </Card>
  );
}
