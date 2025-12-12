import React from 'react';
import { Play, Download } from 'lucide-react';

interface AudioPlayerProps {
    audioUrl: string;
    transcript: string;
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({ audioUrl, transcript }) => {
    return (
        <div className="glass-panel rounded-2xl p-6 mt-8 border-t border-white/10">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center">
                    <div className="w-8 h-8 rounded-lg bg-green-500/20 flex items-center justify-center mr-3 text-green-400">
                        🎧
                    </div>
                    <h2 className="text-xl font-semibold text-white">Your Podcast</h2>
                </div>
                <a
                    href={audioUrl}
                    download="podcast.mp3"
                    className="flex items-center px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm font-medium transition-colors border border-slate-700"
                >
                    <Download className="w-4 h-4 mr-2" />
                    Download
                </a>
            </div>

            <div className="mb-8 bg-slate-900/50 rounded-xl p-4 border border-slate-800">
                <audio controls className="w-full h-10 accent-blue-500" src={audioUrl}>
                    Your browser does not support the audio element.
                </audio>
            </div>

            <div>
                <h3 className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wider">Transcript</h3>
                <div className="bg-slate-900/50 p-6 rounded-xl h-96 overflow-y-auto text-slate-300 whitespace-pre-wrap border border-slate-800 font-light leading-relaxed scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                    {transcript}
                </div>
            </div>
        </div>
    );
};
