import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface DevicePropertiesProps {
  device: any | null;
  onSave: (updatedDevice: any) => void;
  onClose: () => void;
}

export const DeviceProperties: React.FC<DevicePropertiesProps> = ({ device, onSave, onClose }) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    address: device?.address || '',
    zone: device?.zone || '',
    location: device?.location || '',
    type: device?.type || 'smoke',
    heightAFF: device?.heightAFF || '',
    manufacturer: device?.manufacturer || '',
    model: device?.model || '',
    sensitivity: device?.sensitivity || 'standard',
    coverageArea: device?.coverageArea || '',
    status: device?.status || 'normal',
    lastTestDate: device?.lastTestDate || ''
  });

  if (!device) {
    return (
      <div className="bg-slate-800 border-l border-slate-700 p-4 text-center text-slate-500">
        {t('fireAlarm.selectDevice')}
      </div>
    );
  }

  const handleChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = () => {
    onSave({ ...device, ...formData });
  };

  return (
    <Card className="border-slate-700 bg-slate-800/80 w-80 absolute right-0 top-0 bottom-0 z-10 shadow-lg">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg text-slate-100">
            {t('fireAlarm.deviceProperties')}
          </CardTitle>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200"
          >
            ✕
          </Button>
        </div>
      </CardHeader>
      <CardContent className="overflow-y-auto h-[calc(100%-80px)] p-4">
        <div className="space-y-4">
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.address')}</Label>
            <Input
              value={formData.address}
              onChange={(e) => handleChange('address', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.addressPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.zone')}</Label>
            <Input
              value={formData.zone}
              onChange={(e) => handleChange('zone', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.zonePlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.location')}</Label>
            <Input
              value={formData.location}
              onChange={(e) => handleChange('location', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.locationPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.detectorType')}</Label>
            <Select value={formData.type} onValueChange={(value) => handleChange('type', value)}>
              <SelectTrigger className="bg-slate-900 border-slate-600 text-white mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="smoke">{t('fireAlarm.smokeDet')}</SelectItem>
                <SelectItem value="heat">{t('fireAlarm.heatDet')}</SelectItem>
                <SelectItem value="pull">{t('fireAlarm.pullStation')}</SelectItem>
                <SelectItem value="horns">{t('fireAlarm.hornStrobe')}</SelectItem>
                <SelectItem value="speaker">{t('fireAlarm.speaker')}</SelectItem>
                <SelectItem value="facp">{t('fireAlarm.facp')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.heightAff')}</Label>
            <Input
              value={formData.heightAFF}
              onChange={(e) => handleChange('heightAFF', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.heightAffPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.manufacturer')}</Label>
            <Input
              value={formData.manufacturer}
              onChange={(e) => handleChange('manufacturer', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.manufacturerPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.model')}</Label>
            <Input
              value={formData.model}
              onChange={(e) => handleChange('model', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.modelPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.sensitivity')}</Label>
            <Select value={formData.sensitivity} onValueChange={(value) => handleChange('sensitivity', value)}>
              <SelectTrigger className="bg-slate-900 border-slate-600 text-white mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="high">{t('fireAlarm.high')}</SelectItem>
                <SelectItem value="standard">{t('fireAlarm.standard')}</SelectItem>
                <SelectItem value="low">{t('fireAlarm.low')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.coverageArea')}</Label>
            <Input
              value={formData.coverageArea}
              onChange={(e) => handleChange('coverageArea', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
              placeholder={t('fireAlarm.coverageAreaPlaceholder')}
            />
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.status')}</Label>
            <Select value={formData.status} onValueChange={(value) => handleChange('status', value)}>
              <SelectTrigger className="bg-slate-900 border-slate-600 text-white mt-1">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-700">
                <SelectItem value="normal">{t('fireAlarm.normal')}</SelectItem>
                <SelectItem value="active">{t('fireAlarm.active')}</SelectItem>
                <SelectItem value="fault">{t('fireAlarm.fault')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          <div>
            <Label className="text-slate-300 text-sm">{t('fireAlarm.lastTest')}</Label>
            <Input
              type="date"
              value={formData.lastTestDate}
              onChange={(e) => handleChange('lastTestDate', e.target.value)}
              className="bg-slate-900 border-slate-600 text-white mt-1"
            />
          </div>
          
          <div className="pt-4">
            <Button 
              className="w-full bg-red-600 hover:bg-red-700 text-white border-none"
              onClick={handleSave}
            >
              {t('common.save')}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};