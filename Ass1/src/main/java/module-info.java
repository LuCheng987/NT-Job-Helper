module com.example.ass1 {
    requires javafx.controls;
    requires javafx.fxml;


    opens com.example.ass1 to javafx.fxml;
    exports com.example.ass1;
}