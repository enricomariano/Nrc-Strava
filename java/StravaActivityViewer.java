import javafx.application.Application;
import javafx.scene.Scene;
import javafx.scene.chart.*;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;
import org.json.*;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class StravaActivityViewer extends Application {

    private static final String BASE_URL = "https://nrc-strava.onrender.com";

    public static void main(String[] args) {
        launch(args);
    }

    @Override
    public void start(Stage stage) throws Exception {
        List<JSONObject> activities = loadActivities();
        if (activities.isEmpty()) {
            System.out.println("⚠️ Nessuna attività trovata");
            return;
        }

        JSONObject act = activities.get(0);
        JSONObject stream = fetchStream(act.getInt("id"));

        VBox root = new VBox();
        root.getChildren().addAll(
            createChart("HR (bpm)", stream.optJSONArray("heartrate")),
            createChart("Velocità (km/h)", stream.optJSONArray("velocity_smooth")),
            createChart("Altitudine (m)", stream.optJSONArray("altitude")),
            createChart("Watt", stream.optJSONArray("watts"))
        );

        stage.setTitle("📊 Strava Stream Viewer");
        stage.setScene(new Scene(root, 800, 600));
        stage.show();
    }

    private LineChart<Number, Number> createChart(String label, JSONArray data) {
        NumberAxis xAxis = new NumberAxis();
        NumberAxis yAxis = new NumberAxis();
        xAxis.setLabel("Tempo (s)");
        yAxis.setLabel(label);

        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setTitle(label);
        XYChart.Series<Number, Number> series = new XYChart.Series<>();
        series.setName(label);

        if (data != null) {
            for (int i = 0; i < data.length(); i++) {
                series.getData().add(new XYChart.Data<>(i, data.getDouble(i)));
            }
        }

        chart.getData().add(series);
        return chart;
    }

    private List<JSONObject> loadActivities() throws IOException {
        URL url = new URL(BASE_URL + "/download-json");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            StringBuilder json = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) json.append(line);
            JSONArray array = new JSONArray(json.toString());

            List<JSONObject> list = new ArrayList<>();
            for (int i = 0; i < array.length(); i++) {
                list.add(array.getJSONObject(i));
            }
            return list;
        }
    }

    private JSONObject fetchStream(int activityId) throws IOException {
        URL url = new URL(BASE_URL + "/streams/" + activityId);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");

        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            StringBuilder json = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) json.append(line);
            return new JSONObject(json.toString());
        }
    }
}
